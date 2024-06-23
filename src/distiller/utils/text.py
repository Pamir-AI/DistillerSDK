from PIL import Image, ImageDraw, ImageFont
from distiller.constants import EINK_WIDTH, EINK_HEIGHT, DEFAULT_FONT_PATH
from typing import Optional


def trim_text_chunk(text: str, font_path: Optional[str] = DEFAULT_FONT_PATH, font_size: Optional[int] = 20, bounding_box: list[int] = [0, 0, EINK_WIDTH, EINK_HEIGHT]) -> list[str]:
    font = ImageFont.truetype(font_path, font_size)
    draw = ImageDraw.Draw(Image.new('1', (EINK_WIDTH, EINK_HEIGHT)))
    line_height = font_size + 2  # Assuming line height is roughly equal to font size
    x, y = bounding_box[:2]
    max_width, max_height = bounding_box[2] - x, bounding_box[3] - y
    lines = []
    line = []
    for word in text.split():
        # Test if adding this word to the current line would exceed the max width
        test_line = ' '.join(line + [word])
        w, _ = draw.textsize(test_line, font=font)
        if w <= max_width:
            line.append(word)  # If not, add the word to the current line
        else:
            # If the line is too long, start a new line
            if (len(lines) + 1) * line_height >= max_height:
                return lines
            lines.append(' '.join(line))
            line = [word]
            
    # Check if adding the last line still fits
    if (len(lines) + 1) * line_height < max_height:
        lines.append(' '.join(line))    
    return lines


def split_text_chunks(text: str, bounding_box: list[int], font_path: Optional[str] = DEFAULT_FONT_PATH, font_size: Optional[int] = 20) -> list[str]:
    font = ImageFont.truetype(font_path, font_size)
    draw = ImageDraw.Draw(Image.new('1', (EINK_WIDTH, EINK_HEIGHT)))
    line_height = font_size + 2  # Assuming line height is roughly equal to font size
    
    x, y = bounding_box[:2]
    max_width, max_height = bounding_box[2] - x, bounding_box[3] - y
    
    for paragraph in text.split('\n'):
        lines = []
        line = []
        for word in paragraph.split():
            # Test if adding this word to the current line would exceed the max width
            test_line = ' '.join(line + [word])
            w, _ = draw.textsize(test_line, font=font)

            if w <= max_width:
                line.append(word)  # If not, add the word to the current line
            else:
                # If the line is too long, start a new line
                if (len(lines) + 1) * line_height >= max_height:
                    yield ' '.join(lines)
                    lines = [] # reset for next chunk
                lines.append(' '.join(line))
                line = [word]
                
        # Check if adding the last line still fits
        if (len(lines) + 1) * line_height < max_height:
            lines.append(' '.join(line))
        
        if lines: yield ' '.join(lines)
