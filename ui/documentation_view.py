"""
Documentation viewer.
Opens markdown documentation in the default web browser.
"""

import webbrowser
import tempfile
import logging
import re

logger = logging.getLogger(__name__)


def open_documentation(doc_filename, theme_manager):
    """
    Open a markdown documentation file in the default web browser.

    Args:
        doc_filename: Name of the markdown file (e.g., 'user_guide.md')
        theme_manager: ThemeManager instance with palette colors
    """
    from app.paths import get_docs_path

    try:
        # Import markdown library
        import markdown

        # Read markdown file
        doc_path = get_docs_path() / doc_filename
        with open(doc_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()

        # Resolve relative image paths to absolute file:// URIs so the browser
        # can load them from the temp file location.
        docs_dir = get_docs_path()
        markdown_content = re.sub(
            r'src="(\.\./[^"]+)"',
            lambda m: 'src="' + (docs_dir / m.group(1)).resolve().as_uri() + '"',
            markdown_content
        )

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

        # Create temporary HTML file
        temp_file = tempfile.NamedTemporaryFile(
            mode='w',
            delete=False,
            suffix='.html',
            encoding='utf-8'
        )
        temp_file.write(full_html)
        temp_file.close()

        # Open in default browser
        webbrowser.open('file://' + temp_file.name)

    except FileNotFoundError:
        logger.error(f"Documentation file not found: {doc_filename}")
    except ImportError:
        logger.error("Markdown library not installed. Please run: pip install markdown")
    except Exception as e:
        logger.error(f"Error opening documentation: {e}", exc_info=True)
