import zlib
from pathlib import Path
import pytest
from PIL import Image
from pypdf import PdfReader
from engine import discover, natural_key, convert, Options, Cancelled


def image(path, size=(40, 60), color=(34, 100, 200), mode='RGB'):
    Image.new(mode, size, color).save(path)
    return path


def test_natural_sort_and_recursive_discovery(tmp_path):
    for name in ['100.png', '10.png', '2.png', '1.png', 'Page 10.png', 'Page 2.png']:
        image(tmp_path / name)
    (tmp_path / 'notes.txt').write_text('not an image')
    sub = tmp_path / 'sub'
    sub.mkdir()
    image(sub / '3.png')
    assert [p.name for p in discover(tmp_path)[0]] == ['1.png', '2.png', '10.png', '100.png', 'Page 2.png', 'Page 10.png']
    assert len(discover(tmp_path, True)[0]) == 7


def test_mixed_formats_corrupt_and_first_frames(tmp_path):
    for ext in ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'tif', 'tiff', 'gif']:
        image(tmp_path / f'good.{ext}')
    (tmp_path / 'bad.png').write_bytes(b'broken')
    (tmp_path / 'notes.txt').write_text('ignored')
    frames = [Image.new('RGB', (40, 60), 'red'), Image.new('RGB', (80, 90), 'blue')]
    frames[0].save(tmp_path / 'animated.gif', save_all=True, append_images=frames[1:])
    frames[0].save(tmp_path / 'multipage.tiff', save_all=True, append_images=frames[1:])
    paths, _ = discover(tmp_path)
    dest = tmp_path / 'mixed.pdf'
    count, skipped = convert(paths, dest)
    assert count == 10 and len(skipped) == 1
    reader = PdfReader(dest, strict=True)
    assert len(reader.pages) == 10
    assert all(len(p.images) == 1 for p in reader.pages)
    assert all(p['/Resources']['/XObject']['/Im0']['/Width'] == 40 for p in reader.pages)


@pytest.mark.parametrize('reverse', [False, True])
def test_exact_order_and_lossless_pixels(tmp_path, reverse):
    colors = [(200, 10, 20), (30, 180, 40), (50, 60, 170), (100, 20, 80)]
    for name, color in zip(['1.png', '2.png', '10.png', '100.png'], colors):
        image(tmp_path / name, color=color)
    paths = sorted(discover(tmp_path)[0], key=natural_key, reverse=reverse)
    dest = tmp_path / 'order.pdf'
    convert(paths, dest)
    for page, color in zip(PdfReader(dest, strict=True).pages, reversed(colors) if reverse else colors):
        assert page.images[0].image.getpixel((0, 0)) == color
    # Manual sequence is passed through unchanged.
    dest2 = tmp_path / 'manual.pdf'
    convert([paths[2], paths[0]], dest2)
    assert PdfReader(dest2).pages[0].images[0].image.getpixel((0, 0)) == (colors[::-1] if reverse else colors)[2]


@pytest.mark.parametrize('mode,expected', [('original', (144, 72)), ('a4', (841.8898, 595.2756)), ('letter', (792, 612))])
def test_page_dimensions_and_aspect_ratio(tmp_path, mode, expected):
    p = image(tmp_path / 'wide.png', (192, 96))
    dest = tmp_path / 'sizing.pdf'
    convert([p], dest, Options(size=mode))
    page = PdfReader(dest, strict=True).pages[0]
    assert tuple(float(x) for x in page.mediabox[2:]) == pytest.approx(expected, abs=.001)
    operands = page.get_contents().operations[1][0]
    assert float(operands[0]) / float(operands[3]) == pytest.approx(2, abs=.00001)


def test_exif_and_transparency(tmp_path):
    p = tmp_path / 'rotated.jpg'
    exif = Image.Exif()
    exif[274] = 6
    Image.new('RGB', (80, 40), 'red').save(p, exif=exif)
    alpha = image(tmp_path / 'transparent.png', (40, 60), (0, 0, 0, 0), 'RGBA')
    dest = tmp_path / 'orientation.pdf'
    convert([p, alpha], dest)
    pages = PdfReader(dest).pages
    assert pages[0].images[0].image.size == (40, 80)
    assert pages[1].images[0].image.getpixel((0, 0)) == (255, 255, 255)


def test_jpeg_is_embedded_unchanged(tmp_path):
    p = image(tmp_path / 'original.jpg')
    dest = tmp_path / 'jpeg.pdf'
    convert([p], dest)
    obj = PdfReader(dest).pages[0]['/Resources']['/XObject']['/Im0']
    assert obj['/Filter'] == '/DCTDecode'
    assert obj._data == p.read_bytes()


def test_compression_does_not_resize(tmp_path):
    p = image(tmp_path / 'image.png', (512, 256))
    dest = tmp_path / 'compressed.pdf'
    convert([p], dest, Options(compress=True))
    obj = PdfReader(dest).pages[0]['/Resources']['/XObject']['/Im0']
    assert obj['/Filter'] == '/DCTDecode'
    assert (obj['/Width'], obj['/Height']) == (512, 256)


def test_large_folder(tmp_path):
    for number in range(125):
        image(tmp_path / f'{number}.png', size=(100 + number, 80))
    paths, _ = discover(tmp_path)
    calls = []
    dest = tmp_path / 'large.pdf'
    count, skipped = convert(paths, dest, progress=lambda done, total: calls.append((done, total)))
    assert count == 125 and not skipped
    pages = PdfReader(dest, strict=True).pages
    assert len(pages) == 125
    assert [p.images[0].image.width for p in pages] == list(range(100, 225))
    assert calls[-1] == (125, 125)


def test_overwrite_cancel_and_failure_cleanup(tmp_path):
    p = image(tmp_path / 'image.png')
    dest = tmp_path / 'exists.pdf'
    dest.write_bytes(b'original')
    with pytest.raises(FileExistsError):
        convert([p], dest)
    assert dest.read_bytes() == b'original'
    with pytest.raises(Cancelled):
        convert([p], dest, Options(overwrite=True), cancelled=lambda: True)
    assert dest.read_bytes() == b'original'
    assert not list(tmp_path.glob('.imagepdf-*'))
    convert([p], dest, Options(overwrite=True))
    assert len(PdfReader(dest).pages) == 1


def test_empty_and_all_corrupt_leave_no_output(tmp_path):
    dest = tmp_path / 'empty.pdf'
    with pytest.raises(ValueError):
        convert([], dest)
    bad = tmp_path / 'bad.png'
    bad.write_bytes(b'not a picture')
    with pytest.raises(ValueError):
        convert([bad], dest)
    assert not dest.exists()
    assert not list(tmp_path.glob('.imagepdf-*'))


def test_no_clobber_if_destination_appears_mid_conversion(tmp_path):
    p = image(tmp_path / 'image.png')
    dest = tmp_path / 'race.pdf'
    def create_existing(done, total):
        dest.write_bytes(b'created by another process')
    with pytest.raises(FileExistsError):
        convert([p], dest, progress=create_existing)
    assert dest.read_bytes() == b'created by another process'
