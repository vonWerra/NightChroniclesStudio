import importlib
m = importlib.import_module('studio_gui.src.main')
print('module file =', getattr(m, '__file__', None))
print('has preview_selected attribute on class:', hasattr(m.PostProcessTab, 'preview_selected'))
# print the function object repr
if hasattr(m.PostProcessTab, 'preview_selected'):
    print('preview_selected:', m.PostProcessTab.preview_selected)
else:
    print('preview_selected not found')

