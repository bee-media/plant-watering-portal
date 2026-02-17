#!/usr/bin/env python3
"""
Генератор иконок для PWA
Создает простые иконки с символом растения
"""

from PIL import Image, ImageDraw, ImageFont
import os

# Создаем директорию для иконок
icons_dir = 'static/icons'
os.makedirs(icons_dir, exist_ok=True)

# Размеры иконок
sizes = [72, 96, 128, 144, 152, 192, 384, 512]

# Цвета
bg_color = (76, 175, 80)  # Зеленый
icon_color = (255, 255, 255)  # Белый

for size in sizes:
    # Создаем изображение
    img = Image.new('RGB', (size, size), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Рисуем простое растение (лист)
    # Стебель
    stem_width = max(2, size // 40)
    stem_x = size // 2
    stem_y1 = int(size * 0.3)
    stem_y2 = int(size * 0.8)
    draw.line([(stem_x, stem_y1), (stem_x, stem_y2)], fill=icon_color, width=stem_width)
    
    # Листья (эллипсы)
    leaf_width = size // 3
    leaf_height = size // 4
    
    # Левый лист
    left_x = stem_x - leaf_width // 2
    left_y = int(size * 0.4)
    draw.ellipse([left_x - leaf_width, left_y, left_x, left_y + leaf_height], 
                 fill=icon_color, outline=icon_color)
    
    # Правый лист
    right_x = stem_x + leaf_width // 2
    right_y = int(size * 0.5)
    draw.ellipse([right_x, right_y, right_x + leaf_width, right_y + leaf_height], 
                 fill=icon_color, outline=icon_color)
    
    # Верхний лист (больше)
    top_leaf_width = int(leaf_width * 1.3)
    top_leaf_height = int(leaf_height * 1.2)
    top_x = stem_x - top_leaf_width // 2
    top_y = int(size * 0.2)
    draw.ellipse([top_x, top_y, top_x + top_leaf_width, top_y + top_leaf_height], 
                 fill=icon_color, outline=icon_color)
    
    # Сохраняем
    filename = f'{icons_dir}/icon-{size}x{size}.png'
    img.save(filename, 'PNG')
    print(f'Created {filename}')

print('All icons generated successfully!')
