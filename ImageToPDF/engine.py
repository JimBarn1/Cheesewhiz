"""Offline, streaming image-to-PDF conversion. No GUI dependency."""
from __future__ import annotations
import io
import os
import re
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageOps

EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff', '.gif'}


def natural_key(path):
    p = Path(path)
    return (tuple((1, int(s)) if s.isdigit() else (0, s.casefold())
                  for s in re.split(r'(\d+)', p.name)), p.name, str(p).casefold(), str(p))


def discover(folder, recursive=False, cancelled=lambda: False):
    root = Path(folder)
    if not root.is_dir():
        raise ValueError('Select an existing folder.')
    found, errors = [], []
    def onerror(error):
        errors.append(str(error))
    for parent, dirs, files in os.walk(root, onerror=onerror, followlinks=False):
        if cancelled():
            raise Cancelled()
        for name in files:
            p = Path(parent) / name
            if p.suffix.lower() in EXTENSIONS:
                found.append(p)
        if not recursive:
            dirs.clear()
    return sorted(found, key=natural_key), errors


class Cancelled(Exception):
    pass


@dataclass(frozen=True)
class Options:
    size: str = 'original'
    compress: bool = False
    overwrite: bool = False


class PDFWriter:
    """Writes PDF 1.4 objects directly; only one decoded image is resident."""
    def __init__(self, stream):
        self.f = stream
        self.offsets = [0]
        self.pages = []
        self.f.write(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
        self.catalog = self.reserve()
        self.tree = self.reserve()

    def reserve(self):
        self.offsets.append(0)
        return len(self.offsets) - 1

    def start(self, number):
        self.offsets[number] = self.f.tell()
        self.f.write(f'{number} 0 obj\n'.encode())

    def obj(self, number, data):
        self.start(number)
        self.f.write(data + b'\nendobj\n')

    def page(self, path, options, cancelled):
        # Prepare the image completely before writing objects; decode errors can be skipped.
        with Image.open(path) as source:
            source.seek(0)
            dpi = source.info.get('dpi', (96, 96))
            try:
                dx, dy = float(dpi[0]), float(dpi[1])
                if not (10 <= dx <= 2400 and 10 <= dy <= 2400):
                    dx = dy = 96
            except (TypeError, ValueError, IndexError):
                dx = dy = 96
            orientation = source.getexif().get(274, 1)
            direct = source.format == 'JPEG' and source.mode in ('RGB', 'L') and orientation == 1 and not options.compress
            source.load()
            im = ImageOps.exif_transpose(source)
            if orientation in (5, 6, 7, 8):
                dx, dy = dy, dx
            if im.mode in ('RGBA', 'LA') or 'transparency' in im.info:
                rgba = im.convert('RGBA')
                base = Image.new('RGB', im.size, 'white')
                base.paste(rgba, mask=rgba.getchannel('A'))
                im = base
            elif im.mode not in ('RGB', 'L'):
                im = im.convert('RGB')
            width, height = im.size
            # Disk spool avoids retaining compressed streams for all pages.
            with tempfile.TemporaryFile() as encoded:
                jpeg = direct or options.compress
                if direct:
                    with open(path, 'rb') as original:
                        while chunk := original.read(1024 * 1024):
                            if cancelled():
                                raise Cancelled()
                            encoded.write(chunk)
                elif options.compress:
                    im.save(encoded, 'JPEG', quality=85, subsampling=0)
                else:
                    compressor = zlib.compressobj(6)
                    for y in range(0, height, 64):
                        if cancelled():
                            raise Cancelled()
                        encoded.write(compressor.compress(im.crop((0, y, width, min(y+64, height))).tobytes()))
                    encoded.write(compressor.flush())
                length = encoded.tell()
                encoded.seek(0)
                page_w, page_h = width * 72 / dx, height * 72 / dy
                if options.size != 'original':
                    page_w, page_h = {'a4': (595.2756, 841.8898), 'letter': (612, 792)}[options.size]
                    if width > height:
                        page_w, page_h = page_h, page_w
                # PDF implementations commonly limit page sizes to 14,400 points.
                scale_page = min(1, 14400 / max(page_w, page_h))
                page_w, page_h = page_w * scale_page, page_h * scale_page
                ratio = min(page_w / width, page_h / height)
                draw_w, draw_h = width * ratio, height * ratio
                x, y = (page_w - draw_w) / 2, (page_h - draw_h) / 2
                img_id, content_id, page_id = self.reserve(), self.reserve(), self.reserve()
                self.start(img_id)
                color = 'DeviceGray' if im.mode == 'L' else 'DeviceRGB'
                header = f'<< /Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace /{color} /BitsPerComponent 8 /Filter /{"DCTDecode" if jpeg else "FlateDecode"} /Length {length} >>\nstream\n'
                self.f.write(header.encode())
                while chunk := encoded.read(1024 * 1024):
                    if cancelled():
                        raise Cancelled()
                    self.f.write(chunk)
                self.f.write(b'\nendstream\nendobj\n')
                commands = f'q {draw_w:.6f} 0 0 {draw_h:.6f} {x:.6f} {y:.6f} cm /Im0 Do Q\n'.encode()
                self.obj(content_id, f'<< /Length {len(commands)} >>\nstream\n'.encode() + commands + b'endstream')
                self.obj(page_id, f'<< /Type /Page /Parent {self.tree} 0 R /MediaBox [0 0 {page_w:.6f} {page_h:.6f}] /Resources << /XObject << /Im0 {img_id} 0 R >> >> /Contents {content_id} 0 R >>'.encode())
                self.pages.append(page_id)

    def finish(self):
        self.obj(self.tree, f'<< /Type /Pages /Count {len(self.pages)} /Kids [ '.encode() + ' '.join(f'{p} 0 R' for p in self.pages).encode() + b' ] >>')
        self.obj(self.catalog, f'<< /Type /Catalog /Pages {self.tree} 0 R >>'.encode())
        offset = self.f.tell()
        self.f.write(f'xref\n0 {len(self.offsets)}\n0000000000 65535 f \n'.encode())
        for pos in self.offsets[1:]:
            self.f.write(f'{pos:010d} 00000 n \n'.encode())
        self.f.write(f'trailer\n<< /Size {len(self.offsets)} /Root {self.catalog} 0 R >>\nstartxref\n{offset}\n%%EOF\n'.encode())


def convert(paths, destination, options=Options(), progress=lambda done, total: None, cancelled=lambda: False):
    paths = list(paths)
    destination = Path(destination).absolute()
    if not paths:
        raise ValueError('There are no images to convert.')
    if options.size not in ('original', 'a4', 'letter'):
        raise ValueError('Unknown page size.')
    if destination.suffix.lower() != '.pdf':
        raise ValueError('Choose a filename ending in .pdf.')
    if any(Path(p).resolve() == destination.resolve() for p in paths):
        raise ValueError('The output cannot replace an input image.')
    if destination.exists() and not options.overwrite:
        raise FileExistsError('The output already exists. Choose another name or confirm replacement.')
    fd, temp = tempfile.mkstemp(prefix='.imagepdf-', suffix='.tmp', dir=destination.parent)
    skipped = []
    try:
        with os.fdopen(fd, 'wb') as f:
            writer = PDFWriter(f)
            for index, path in enumerate(paths, 1):
                if cancelled():
                    raise Cancelled()
                # Decode failures are skippable; output I/O failures must abort.
                try:
                    with Image.open(path) as check:
                        check.seek(0)
                        check.load()
                except (OSError, ValueError, Image.DecompressionBombError) as error:
                    skipped.append((str(path), str(error)))
                else:
                    writer.page(path, options, cancelled)
                progress(index, len(paths))
            if not writer.pages:
                raise ValueError('None of the selected files could be decoded. No PDF was created.')
            writer.finish()
            f.flush()
            os.fsync(f.fileno())
            count = len(writer.pages)
        if cancelled():
            raise Cancelled()
        if options.overwrite:
            os.replace(temp, destination)
        elif os.name == 'nt':
            os.rename(temp, destination)  # Windows rename refuses existing destinations.
        else:
            os.link(temp, destination)  # Atomic no-clobber publication on POSIX.
            os.unlink(temp)
        return count, skipped
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
