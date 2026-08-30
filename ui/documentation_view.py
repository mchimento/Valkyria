"""
Documentation viewer.
Opens markdown documentation in the default web browser.
"""

import base64
import mimetypes
import platform
import webbrowser
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def open_documentation(doc_filename, theme_manager):
    """
    Open a markdown documentation file in the default web browser.

    Args:
        doc_filename: Name of the markdown file (e.g., 'user_guide.md')
        theme_manager: ThemeManager instance with palette colors
    """
    from app.paths import get_docs_path, get_user_data_path

    try:
        # Import markdown library
        import markdown

        # Read markdown file
        doc_path = get_docs_path() / doc_filename
        with open(doc_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()

        # Embed referenced images as base64 data: URIs rather than
        # resolving to a file:// path — a snap-confined browser (e.g.
        # Ubuntu's default Firefox package) can't read arbitrary
        # filesystem paths at all (confirmed: this failed even from the
        # user's own home directory, since snap's home interface also
        # excludes hidden dot-directories — there's no filesystem location
        # guaranteed accessible), so the image has to travel inside the
        # HTML itself instead of being referenced externally.
        docs_dir = get_docs_path()

        def _embed_image(match):
            image_path = (docs_dir / match.group(1)).resolve()
            try:
                mime_type, _ = mimetypes.guess_type(str(image_path))
                with open(image_path, 'rb') as img_f:
                    encoded = base64.b64encode(img_f.read()).decode('ascii')
                return f'src="data:{mime_type or "application/octet-stream"};base64,{encoded}"'
            except Exception:
                logger.exception("Failed to embed image %s", image_path)
                return match.group(0)

        markdown_content = re.sub(r'src="(\.\./[^"]+)"', _embed_image, markdown_content)

        # Preprocess markdown content
        lines = markdown_content.split('\n')
        processed_lines = []

        for line in lines:
            # Convert plain URLs to markdown links
            if 'http://' in line or 'https://' in line:
                if not re.search(r'\[.+?\]\(https?://.+?\)', line):
                    line = re.sub(
                        r'(?<!\()(https?://[^\s,;)]+)',
                        r'[\1](\1)',
                        line
                    )

            # Convert 2-space nested lists to 4-space (standard markdown)
            # This ensures proper nesting in rendered HTML
            match = re.match(r'^(\s*)[*-] ', line)
            if match:
                indent = match.group(1)
                if len(indent) == 2:
                    # Convert 2-space to 4-space
                    line = '    ' + line[2:]
                elif len(indent) == 4:
                    # Convert 4-space to 8-space (second level)
                    line = '        ' + line[4:]

            processed_lines.append(line)

        markdown_content = '\n'.join(processed_lines)

        # Convert markdown to HTML
        html_content = markdown.markdown(
            markdown_content,
            extensions=[
                'tables',
                'fenced_code',
                'toc'
            ]
        )

        # Get colors from theme palette
        palette = theme_manager.palette
        bg_color = palette.get("bg", "#1e1e1e")
        text_color = palette.get("fg", "#d4d4d4")
        heading_color = palette.get("heading_color", "#4ec9b0")
        link_color = palette.get("link_color", "#569CD6")
        link_hover = palette.get("link_hover", "#77B4E8")
        border_color = palette.get("border", "#404040")

        # Determine if dark theme for code backgrounds
        is_dark = theme_manager.settings.theme.lower() == 'dark'
        if is_dark:
            code_bg = palette.get("tree_bg", "#2d2d2d")
            table_header_bg = palette.get("tree_header", "#2d2d2d")
        else:
            code_bg = palette.get("striped_bg", "#f5f5f5")
            table_header_bg = palette.get("tree_header", "#f0f0f0")

        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{doc_filename.replace('.md', '').replace('_', ' ').title()}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 20px;
            background-color: {bg_color};
            color: {text_color};
        }}
        h1 {{
            font-size: 2.5em;
            color: {heading_color};
            border-bottom: 2px solid {heading_color};
            padding-bottom: 10px;
            margin-top: 30px;
        }}
        h2 {{
            font-size: 2em;
            color: {heading_color};
            margin-top: 30px;
            margin-bottom: 15px;
        }}
        h3 {{
            font-size: 1.5em;
            color: {heading_color};
            margin-top: 25px;
            margin-bottom: 12px;
        }}
        h4 {{
            font-size: 1.2em;
            color: {heading_color};
            margin-top: 20px;
            margin-bottom: 10px;
        }}
        p {{
            margin: 12px 0;
        }}
        a {{
            color: {link_color};
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
            color: {link_hover};
        }}
        code {{
            background-color: {code_bg};
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.9em;
        }}
        pre {{
            background-color: {code_bg};
            padding: 15px;
            border-radius: 6px;
            overflow-x: auto;
            border: 1px solid {border_color};
        }}
        pre code {{
            background-color: transparent;
            padding: 0;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
            border: 1px solid {border_color};
        }}
        th {{
            background-color: {table_header_bg};
            padding: 12px;
            text-align: left;
            border: 1px solid {border_color};
            font-weight: bold;
        }}
        td {{
            padding: 10px 12px;
            border: 1px solid {border_color};
        }}
        tr:nth-child(even) {{
            background-color: {code_bg};
        }}
        ul, ol {{
            margin: 15px 0;
            padding-left: 30px;
        }}
        li {{
            margin: 8px 0;
        }}
        ul ul, ol ol, ul ol, ol ul {{
            margin: 5px 0;
            padding-left: 25px;
        }}
        ul ul li, ol ol li {{
            margin: 5px 0;
        }}
        hr {{
            border: none;
            border-top: 1px solid {border_color};
            margin: 30px 0;
        }}
        blockquote {{
            border-left: 4px solid {heading_color};
            margin: 20px 0;
            padding-left: 20px;
            color: {text_color};
            opacity: 0.9;
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""

        # Write the HTML to a real file rather than opening it as a
        # data: URI — tried that first, and it failed too: a data: URI
        # embedding the doc's one ~185KB image inline came to ~430KB, and
        # launching a browser with that as a single command-line argument
        # failed outright with "Argument list too long". That's Linux's
        # MAX_ARG_STRLEN, a per-argument cap of PAGE_SIZE*32 (128KB on this
        # system) — confirmed directly, not assumed, by actually invoking
        # `firefox <the 430KB URI>` and getting exactly that shell error.
        # It's a much tighter limit than the ~2MB *total* argv+envp budget
        # (getconf ARG_MAX), which is the one that looks relevant until you
        # hit this one instead.
        #
        # So the image has to live in a real file after all — the fix is
        # *where*, not avoiding a file entirely. Two locations already
        # confirmed blocked for a snap-confined browser (e.g. Ubuntu's
        # default Firefox package, this app's primary target platform):
        # the system temp dir ("File not found" even though the file
        # genuinely existed) and this app's own hidden data directory
        # under the user's home, since snap's home interface specifically
        # excludes dot-directories ("Access to the file was denied" from
        # ~/.tango-studio/...). A non-hidden directory directly under the
        # home directory is what's actually left in what snap's home
        # interface grants. The image stays embedded as base64 *inside*
        # the file's own content (set above) — that's not subject to any
        # argument-length limit, only the short file:// path passed to
        # the browser is.
        #
        # Snap confinement is Linux-specific — there's no equivalent
        # sandboxing restricting a normal desktop browser's file access on
        # Windows or macOS, so this workaround only applies there. Windows/
        # macOS use get_user_data_path() instead, matching every other
        # piece of user data this app writes (settings, logs) rather than
        # introducing a new, Linux-problem-motivated folder that isn't
        # needed on those platforms.
        if platform.system() == "Linux":
            docs_out_dir = Path.home() / "Valkyria"
            docs_out_dir.mkdir(exist_ok=True)
        else:
            docs_out_dir = get_user_data_path()
        out_path = docs_out_dir / f"docs_preview_{doc_filename.replace('.md', '')}.html"
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        webbrowser.open(out_path.resolve().as_uri())

    except FileNotFoundError:
        logger.error(f"Documentation file not found: {doc_filename}")
    except ImportError:
        logger.error("Markdown library not installed. Please run: pip install markdown")
    except Exception as e:
        logger.error(f"Error opening documentation: {e}", exc_info=True)
