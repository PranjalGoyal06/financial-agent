sed -i '' 's/updates = {}/updates: dict = {}/g' app/research/nodes/synthesis.py
sed -i '' 's/errors = \[\]/errors: list[str] = []/g' app/research/nodes/synthesis.py
sed -i '' 's/macro_drivers = \[\]/macro_drivers: list[str] = []/g' app/research/nodes/synthesis.py
