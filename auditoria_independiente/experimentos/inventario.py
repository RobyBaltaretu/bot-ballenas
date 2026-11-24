"""Inventario AST de todo el código Python propio (solo lectura)."""
import ast, os, sys, json
RAIZ = sys.argv[1]
filas = []
for d, subdirs, files in os.walk(RAIZ):
    subdirs[:] = [s for s in subdirs if s not in ('.git', '.venv', 'datos_backtest', 'node_modules', '__pycache__', 'auditoria_independiente')]
    for f in files:
        if not f.endswith('.py'):
            continue
        p = os.path.join(d, f)
        rel = os.path.relpath(p, RAIZ)
        src = open(p, encoding='utf-8-sig').read()
        lineas = src.count('\n') + 1
        try:
            t = ast.parse(src)
        except SyntaxError as e:
            filas.append((rel, lineas, -1, -1, 'SYNTAX ' + str(e)))
            continue
        funcs = [n for n in ast.walk(t) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        clases = [n for n in ast.walk(t) if isinstance(n, ast.ClassDef)]
        doc = (ast.get_docstring(t) or '').strip().split('\n')[0][:110]
        filas.append((rel, lineas, len(funcs), len(clases), doc))
filas.sort()
tot = sum(r[1] for r in filas)
print(json.dumps({'total_lineas': tot, 'archivos': len(filas), 'funciones': sum(max(r[2],0) for r in filas)}))
for r in filas:
    print(f"{r[0]}\t{r[1]}\t{r[2]}\t{r[3]}\t{r[4]}")
