#!/usr/bin/env python3
"""
Prepares and formats all required Windows MSIX application asset images
from existing high-resolution Tauri icons.
"""

import os
import shutil
from pathlib import Path
from PIL import Image

def generate_assets():
    root = Path(__file__).resolve().parent.parent
    src_icons = root / "frontend" / "src-tauri" / "icons"
    out_dir = root / "msix" / "Assets"
    out_dir.mkdir(parents=True, exist_ok=True)

    icon_src = src_icons / "icon.png"
    if not icon_src.exists():
        icon_src = src_icons / "Square310x310Logo.png"

    src_img = Image.open(icon_src).convert("RGBA")

    # 1. Square44x44Logo.png
    sq44_src = src_icons / "Square44x44Logo.png"
    if sq44_src.exists():
        shutil.copy2(sq44_src, out_dir / "Square44x44Logo.png")
    else:
        src_img.resize((44, 44), Image.Resampling.LANCZOS).save(out_dir / "Square44x44Logo.png", "PNG")

    # 2. Square71x71Logo.png
    sq71_src = src_icons / "Square71x71Logo.png"
    if sq71_src.exists():
        shutil.copy2(sq71_src, out_dir / "Square71x71Logo.png")
    else:
        src_img.resize((71, 71), Image.Resampling.LANCZOS).save(out_dir / "Square71x71Logo.png", "PNG")

    # 3. Square150x150Logo.png
    sq150_src = src_icons / "Square150x150Logo.png"
    if sq150_src.exists():
        shutil.copy2(sq150_src, out_dir / "Square150x150Logo.png")
    else:
        src_img.resize((150, 150), Image.Resampling.LANCZOS).save(out_dir / "Square150x150Logo.png", "PNG")

    # 4. Square310x310Logo.png
    sq310_src = src_icons / "Square310x310Logo.png"
    if sq310_src.exists():
        shutil.copy2(sq310_src, out_dir / "Square310x310Logo.png")
    else:
        src_img.resize((310, 310), Image.Resampling.LANCZOS).save(out_dir / "Square310x310Logo.png", "PNG")

    # 5. StoreLogo.png (50x50)
    store_src = src_icons / "StoreLogo.png"
    if store_src.exists():
        shutil.copy2(store_src, out_dir / "StoreLogo.png")
    else:
        src_img.resize((50, 50), Image.Resampling.LANCZOS).save(out_dir / "StoreLogo.png", "PNG")

    # 6. Wide310x150Logo.png (310x150 wide tile)
    wide_img = Image.new("RGBA", (310, 150), (15, 23, 42, 255)) # Dark slate background (#0f172a)
    # Fit 120x120 icon in the center
    icon_120 = src_img.resize((120, 120), Image.Resampling.LANCZOS)
    wide_img.paste(icon_120, ((310 - 120) // 2, (150 - 120) // 2), icon_120)
    wide_img.save(out_dir / "Wide310x150Logo.png", "PNG")

    # 7. SplashScreen.png (620x300 splash screen)
    splash_img = Image.new("RGBA", (620, 300), (15, 23, 42, 255))
    # Fit 180x180 icon in the center
    icon_180 = src_img.resize((180, 180), Image.Resampling.LANCZOS)
    splash_img.paste(icon_180, ((620 - 180) // 2, (300 - 180) // 2), icon_180)
    splash_img.save(out_dir / "SplashScreen.png", "PNG")

    print(f"Successfully generated MSIX assets in {out_dir}")
    for item in sorted(out_dir.glob("*.png")):
        print(f" - {item.name} ({item.stat().st_size} bytes)")

if __name__ == "__main__":
    generate_assets()
