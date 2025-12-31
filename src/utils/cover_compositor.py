# New file: cover_compositor.py
from PIL import Image, ImageEnhance
from io import BytesIO
import base64
import math
from collections import Counter
from pathlib import Path

from common.logging import Logger

class CoverCompositor:
    """Creates composite cover artwork from individual cover images.

    Provides utilities to arrange multiple covers into a grid and export the result as an embeddable image.
    """
    def __init__(self, covers_dir: Path, logger: Logger=None):
        """Initializes the compositor with a covers directory and optional logger.

        Stores paths and logging configuration so composite images can be built and diagnostics recorded.

        Args:
            covers_dir: Filesystem path where individual cover images are stored.
            logger: Optional logger instance used for warnings and diagnostic messages.
        """
        self.covers_dir = covers_dir
        self._logger = logger

    def _build_fill_covers(self, cover_paths: list[str]) -> tuple[list[str], int]:
        """Determines the grid size and expanded list of covers to fill all grid cells.

        Computes a square grid dimension based on unique covers and repeats higher-frequency covers to fill remaining cells.

        Args:
            cover_paths: List of cover filenames, possibly with duplicates for weighting.

        Returns:
            tuple[list[str], int]: A tuple containing the ordered list of covers to use and the computed grid size.
        """
        cover_counts = Counter(cover_paths)
        unique_covers = list(dict.fromkeys(cover_paths))  # preserve order

        n_unique = len(unique_covers)
        grid_size = math.ceil(math.sqrt(n_unique))
        total_cells = grid_size**2

        cells_needed = total_cells - n_unique
        if cells_needed > 0:
            sorted_by_freq = sorted(
                unique_covers, key=lambda c: cover_counts[c], reverse=True
            )
            repeats: list[str] = []
            for cover in sorted_by_freq:
                if cells_needed <= 0:
                    break
                repeats.append(cover)
                cells_needed -= 1
            fill_covers = unique_covers + repeats
        else:
            fill_covers = unique_covers

        return fill_covers, grid_size

    def _load_tiles(self, fill_covers: list[str], tile_size: int = 400) -> list[Image.Image]:
        """Loads cover images and converts them into uniformly sized square tiles.

        Opens each cover file, applies basic enhancement, and returns a list of cropped and resized tile images.

        Args:
            fill_covers: Ordered list of cover filenames to be used as tiles.
            tile_size: Target width and height in pixels for each square tile.

        Returns:
            list[Image.Image]: A list of processed PIL Image objects ready for compositing.
        """
        tiles: list[Image.Image] = []
        for path in fill_covers:
            full_path = self.covers_dir / Path(path).name
            if not full_path.exists():
                continue
            try:
                img = Image.open(full_path).convert("RGB")
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.05)

                w, h = img.size
                crop = min(w, h)
                left = (w - crop) // 2
                top = (h - crop) // 2
                square = img.crop((left, top, left + crop, top + crop))

                tiles.append(square.resize((tile_size, tile_size), Image.LANCZOS))
            except Exception as e:
                self._logger.warning(f"Failed to load cover {full_path}: {e}")
        return tiles

    def _compose_grid(
        self, tiles: list[Image.Image], grid_size: int, tile_size: int = 400
    ) -> Image.Image:
        """Builds a single composite image by arranging tiles into a square grid.

        Places each tile into its grid cell on a new background image and returns the combined result.

        Args:
            tiles: List of tile images to arrange in the grid.
            grid_size: Number of tiles per row and column in the square grid.
            tile_size: Width and height in pixels of each tile.

        Returns:
            Image.Image: The composed grid image.
        """
        composite = Image.new(
            "RGB", (tile_size * grid_size, tile_size * grid_size), (30, 30, 30)
        )
        for i, tile in enumerate(tiles):
            x = (i % grid_size) * tile_size
            y = (i // grid_size) * tile_size
            composite.paste(tile, (x, y))
        return composite

    def _encode_image_to_data_url(self, image: Image.Image) -> str:
        """Encodes a PIL image as a JPEG base64 data URL.

        Converts the provided image into an in-memory JPEG and returns a data URL string suitable for embedding.

        Args:
            image: The PIL Image instance to encode.

        Returns:
            str: A data URL string containing the base64-encoded JPEG image.
        """
        buffered = BytesIO()
        image.save(buffered, format="JPEG", quality=95, optimize=True)
        return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"

    def generate_grid_composite(self, cover_paths: list[str]) -> str:
        """Generates a composite cover image from multiple individual cover files.

        Builds a square grid of cover tiles and returns the result as a base64-encoded JPEG data URL.

        Args:
            cover_paths: List of cover filenames (may contain duplicates for weighting).

        Returns:
            str: A data URL string containing the base64-encoded JPEG composite image.

        Raises:
            ValueError: If no cover paths are provided or no images can be loaded.
        """
        if not cover_paths:
            raise ValueError("No covers provided")

        fill_covers, grid_size = self._build_fill_covers(cover_paths)
        tiles = self._load_tiles(fill_covers)

        if not tiles:
            raise ValueError("No images could be loaded")

        composite = self._compose_grid(tiles, grid_size)
        return self._encode_image_to_data_url(composite)