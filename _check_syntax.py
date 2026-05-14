import ast, sys

files = ["app/skills_api.py", "app/server.py", "app/chat_agent.py"]
ok = True
for f in files:
    try:
        with open(f, encoding="utf-8") as fh:
            src = fh.read()
        ast.parse(src)
        print(f"OK: {f}")
    except SyntaxError as e:
        print(f"SYNTAX ERROR in {f}: {e}")
        ok = False
    except Exception as e:
        print(f"ERROR in {f}: {e}")
        ok = False

sys.exit(0 if ok else 1)
