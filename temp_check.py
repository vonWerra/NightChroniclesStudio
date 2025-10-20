import inspect, sys
import studio_gui.src.main as m
print('module file =', getattr(m,'__file__', None))
print('has preview:', hasattr(m.PostProcessTab,'preview_selected'))
print('sys.path first entries:', sys.path[:5])
if hasattr(m.PostProcessTab,'preview_selected'):
    src = inspect.getsource(m.PostProcessTab.preview_selected)
    print('--- source (first 400 chars) ---')
    print(src[:400])
