![QR Codes](../images/qr-code.png){ align=right width="90" }

# QR Code Generation

## 🎯 What the Package Does

The `qr_generator` package creates **PNG QR‑code** images that encode a mixtape’s public URL.
Two flavours are offered:

| Function | Output | Extra visual elements |
| ---------- | -------- | ---------------------- |
| `generate_mixtape_qr` | Plain QR code (square) | Optional centred logo (SVG/PNG) |
| `generate_mixtape_qr_with_cover` | Composite image (cover → title banner → QR) | Optional cover art, title banner, centred logo |

Both functions return **raw `bytes`** (PNG data) ready to be sent as a Flask `Response` or saved to disk.

## 🔧 Installation & Dependencies

| Setting | Where it lives | Default | Remarks |
| ------ | ------------- | ------- | ------- |
| **`qrcode`** (Python library) | `project.toml` / `uv.lock` | `>=7.4` | Required for both endpoints. |
| **`Pillow`** (image handling) | `project.toml` | `>=10.0` | Needed for compositing the logo/cover. |
| **Static logo files** | `static/logo.svg` or `static/logo.png` | — | The blueprint prefers SVG; falls back to PNG. |
| **Cover directory** | `app.config["COVER_DIR"]` (set in config.py) | `collection-data/mixtapes/covers` | Used only by the download endpoint. |
| **Cache-Control** | Hard-coded in the view (`public, max-age=3600`). | — | Adjust in the source if you need a different TTL. |

## ⚠️ Error Handling

| Situation | Raised Exception | Message (visible to caller) |
| --------- | --------------- | --------------------------- |
| `qrcode` library missing | `ImportError` (raised at the top of each public function) | `"qrcode library not installed. Install with: uv add qrcode pillow"` |
| Logo or cover path does not exist | Silently ignored — the function falls back to a plain QR or a QR without cover. Errors are printed to stdout (`print`) but not propagated. | — |
| `Pillow` fails to open an image (corrupt file) | Caught inside the helper; continues processing | Prints `"Failed to load cover: …"` or `"Failed to add logo to QR code: …"` and continues with the rest of the image. |
| Invalid `size` / `qr_size` (negative, zero) | Not explicitly validated — `Pillow` raises a `ValueError` during resize | Exception propagates to the caller (treated as a 500 error in the Flask view). |

**Best practice** – Validate user‑supplied sizes before calling the functions, or wrap the call in a `try/except` block and return a friendly error page.

## 🔌 API

### ::: src.qr_generator.qr_generator
