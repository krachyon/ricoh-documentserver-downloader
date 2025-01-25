# What is this?

A script to mass download/delete files from the document server of an Aficio MP C2050/C2550.

Might work with other models, that use the same interface.

# Usage
* run `$ poetry install`
* in `main.py` change `PRINTER_IP` to the ip or hostname of the printer 
* in `main.py:run()` comment in/out what the script is supposed to do.
currently your choice is between `get_all_pdfs` and `delete_all_documents` which should be somewhat self explanatory
* run it with `poetry run python main.py`