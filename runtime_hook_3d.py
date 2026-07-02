"""Runtime hook for WARFRONT3D PyInstaller build.
Ensures Panda3D display libraries and fonts are available."""
import sys
import os
import shutil

if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS

    # Add bundle dir and panda3d subdirs to PATH so DLLs can be found
    for sub in ('', 'panda3d', os.path.join('panda3d', 'core'), 'etc'):
        p = os.path.join(bundle_dir, sub)
        if os.path.isdir(p) and p not in os.environ.get('PATH', ''):
            os.environ['PATH'] = p + os.pathsep + os.environ.get('PATH', '')

    # Create a minimal Config.prc that loads the OpenGL display
    etc_dir = os.path.join(bundle_dir, 'etc')
    os.makedirs(etc_dir, exist_ok=True)
    prc_path = os.path.join(etc_dir, 'Config.prc')
    if not os.path.exists(prc_path):
        with open(prc_path, 'w') as f:
            f.write("load-display pandagl\n")
            f.write("aux-display pandadx9\n")
            f.write("aux-display pandagl\n")
            f.write("notify-level-util error\n")
            f.write("notify-level-egg error\n")
            f.write("model-cache-dir\n")

    os.environ['PANDA_PRC_DIR'] = etc_dir

    # Copy a system font to the bundle directory so Ursina can find it
    fonts_src = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
    for font_name in ('arial.ttf', 'segoeui.ttf', 'calibri.ttf', 'consola.ttf'):
        src = os.path.join(fonts_src, font_name)
        dst = os.path.join(bundle_dir, font_name)
        if os.path.isfile(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass
        if os.path.exists(dst):
            break

    # Also copy font to CWD for additional fallback
    cwd = os.getcwd()
    for font_name in ('arial.ttf', 'segoeui.ttf', 'calibri.ttf'):
        src = os.path.join(fonts_src, font_name)
        dst = os.path.join(cwd, font_name)
        if os.path.isfile(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass
        if os.path.exists(dst):
            break
