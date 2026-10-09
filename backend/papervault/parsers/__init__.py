from .pdfium import inspect_pdf, render_region


def parse_pdf(source, output_dir, models_dir, on_progress=None):
    from .docling_parser import parse_pdf as convert
    return convert(source, output_dir, models_dir, on_progress)


__all__ = ["parse_pdf", "render_region", "inspect_pdf"]
