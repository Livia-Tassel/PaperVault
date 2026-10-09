# PyInstaller onedir: heavyweight ML dependencies stay in _internal beside the executable.
from pathlib import Path
from importlib.util import find_spec
from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

root = Path(SPECPATH).parent
if find_spec('docling') is None:
    raise SystemExit('Full desktop release requires the Docling module; install the parser extra.')
datas, binaries, hiddenimports = [], [], [
    'uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl', 'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan.on', 'papervault',
]
# Imports made by parser factories, model registries and entry points are not all
# statically discoverable. Keep their data and metadata with explicit hooks.
for package in ('docling', 'docling_core', 'docling_parse', 'docling_ibm_models', 'pypdfium2', 'cv2'):
    try:
        package_datas, package_bins, package_imports = collect_all(package)
        datas += package_datas
        binaries += package_bins
        hiddenimports += package_imports
    except ImportError:
        if package == 'docling':
            raise SystemExit('Full desktop release requires Docling; install .[dev,parser].')
for distribution in ('papervault', 'docling-slim', 'docling', 'docling-core', 'pypdfium2', 'transformers', 'torch', 'huggingface-hub', 'opencv-python-headless'):
    try:
        datas += copy_metadata(distribution)
    except Exception:
        pass
datas += collect_data_files('latex2mathml')
datas.append((str(root / 'backend' / 'papervault' / 'migrations'), 'papervault/migrations'))
for path in (root / 'LICENSE', root / 'docs' / 'THIRD_PARTY_NOTICES.md', root / 'docs' / 'python-dependencies.json'):
    if path.exists():
        datas.append((str(path), 'licenses'))
if (root / 'docs' / 'third-party-licenses').is_dir():
    datas.append((str(root / 'docs' / 'third-party-licenses'), 'licenses/third-party'))

a = Analysis(
    [str(root / 'backend' / 'papervault' / '__main__.py')],
    pathex=[str(root / 'backend')], binaries=binaries, datas=datas,
    hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[],
    excludes=['tkinter', 'IPython', 'matplotlib.tests', 'pytest'], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='papervault-backend',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=True, disable_windowed_traceback=False, contents_directory='_internal')
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='papervault-backend')
