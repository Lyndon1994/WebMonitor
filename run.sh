#!/bin/bash
python3 manage.py migrate
python3 manage.py initadmin --username $2 --password $3
python3 manage.py runserver 0.0.0.0:$1 --noreload
