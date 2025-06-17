from PIL import Image, ImageDraw, ImageFont
import io
import os

def generate_certificate_image(user_name, course_name, tutor_name, completion_date):
    # Load base certificate template
    template_path = 'static/certificate_template.png'
    image = Image.open(template_path)

    draw = ImageDraw.Draw(image)

    # Load fonts (adjust path and size)
    font_path = "static/fonts/Roboto-Bold.ttf"
    font_large = ImageFont.truetype(font_path, 60)
    font_medium = ImageFont.truetype(font_path, 40)

    # Customize coordinates to match your template layout
    draw.text((600, 500), user_name, fill="black", font=font_large)
    draw.text((600, 600), course_name, fill="black", font=font_medium)
    draw.text((600, 700), tutor_name, fill="black", font=font_medium)
    draw.text((600, 800), completion_date, fill="black", font=font_medium)

    # Save to buffer
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
