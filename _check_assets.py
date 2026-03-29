import pathlib 
code = pathlib.Path('ui/assets_page.py').read_text(encoding='utf-8') 
compile(code, 'ui/assets_page.py', 'exec') 
print('syntax ok') 
