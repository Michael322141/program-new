import sys
import re
import requests
import importlib
from importlib.abc import PathEntryFinder, Loader
from importlib.util import spec_from_loader

# --- Шаг 3, 9, 10: Перехватчик URL, requests и обработка ошибок ---
def url_hook(some_str):
    if not some_str.startswith(("http://", "https://")):
        raise ImportError
    
    try:
        # Шаг 9: используем requests
        response = requests.get(some_str, timeout=5)
        response.raise_for_status()
    except requests.RequestException as e:
        # Шаг 10: обработка ситуации, когда хост недоступен
        raise ImportError(f"Хост недоступен: {e}")

    data = response.text
    
    # Ищем ссылки на файлы (.py) и папки (/)
    # Для папок сохраняем слэш в конце, чтобы отличать их от файлов
    files = re.findall(r'href="([a-zA-Z_][a-zA-Z0-9_]*\.py)"', data)
    dirs = re.findall(r'href="([a-zA-Z_][a-zA-Z0-9_]*/)"', data)

    # Список доступного: ['myremotemodule', 'mypackage/']
    available_modnames = [f[:-3] for f in files] + dirs
    
    return URLFinder(some_str, available_modnames)


# --- Шаг 3, 11: Поиск модулей и пакетов ---
class URLFinder(PathEntryFinder):
    def __init__(self, url, available):
        self.url = url.rstrip('/')
        self.available = available

    def find_spec(self, name, target=None):
        # Берем последнюю часть имени (для mypackage.mymath это будет mymath)
        module_name = name.split('.')[-1]
        
        if module_name + "/" in self.available:
            # Нашли пакет!
            origin = f"{self.url}/{module_name}/__init__.py"
            loader = URLLoader()
            # Шаг 11: is_package=True и submodule_search_locations 
            # говорят Python, что это папка, и где искать её содержимое
            spec = spec_from_loader(name, loader, origin=origin, is_package=True)
            spec.submodule_search_locations = [f"{self.url}/{module_name}"]
            return spec
            
        elif module_name in self.available:
            # Нашли обычный модуль (.py)
            origin = f"{self.url}/{module_name}.py"
            loader = URLLoader()
            return spec_from_loader(name, loader, origin=origin)
            
        return None


# --- Шаг 3, 9: Загрузчик кода ---
class URLLoader(Loader):
    def create_module(self, target):
        return None

    def exec_module(self, module):
        origin = module.__spec__.origin
        try:
            # Шаг 9: используем requests
            response = requests.get(origin, timeout=5)
            response.raise_for_status()
            source = response.text
        except requests.RequestException as e:
            # Шаг 10: обработка ошибок
            raise ImportError(f"Не удалось загрузить модуль из {origin}: {e}")
        
        # Компилируем и выполняем скачанный код
        code = compile(source, origin, mode="exec")
        exec(code, module.__dict__)


# --- Шаг 5, 7: Регистрация хука ---
if url_hook not in sys.path_hooks:
    sys.path_hooks.insert(0, url_hook)

importlib.invalidate_caches() # Сбрасываем кэш путей
print("Скрипт активации загружен. Хуки установлены.")