from pathlib import Path


TEXT_EXTENSIONS = {".txt", ".md", ".log", ".csv", ".tsv", ".py", ".sql", ".css", ".js", ".html"}
CONFIG_EXTENSIONS = {
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".env",
    ".properties",
    ".xml",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}


def detect_file_kind(path: Path) -> str:
    name = path.name.lower()
    suffix = path.suffix.lower()

    if name in {"dockerfile", ".gitignore"}:
        return "config"
    if suffix in TEXT_EXTENSIONS:
        return "text"
    if suffix in CONFIG_EXTENSIONS:
        return "config"
    if suffix == ".docx":
        return "docx"
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".klp":
        return "klp"
    if suffix in {".xlsx", ".xlsm"}:
        return "xlsx"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    return "binary"
