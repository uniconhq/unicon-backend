#!/bin/sh

pip3 install -r requirements.txt

# fixes cursed problem
# from .exceptions import InvalidKeyError ModuleNotFoundError: No module named 'jwt.exceptions'
# somehow the installation order matters

pip3 uninstall -y pyjwt jwt 
pip3 install jwt
pip3 install pyjwt

# seed database
python3 -m src.unicon_backend.utils.seed

# run CMD command 
exec "$@"


