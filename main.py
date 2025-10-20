import json
import os
with open("./config.json", "r", encoding="utf-8") as f:
    os.environ.update(json.load(f)["env"])

import services
import pkgutil
for _, name, _ in pkgutil.iter_modules(services.__path__):
    exec(f'import services.{name}')

import vetariasn as vt
vt.run()