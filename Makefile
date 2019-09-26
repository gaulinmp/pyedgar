PY?=python3
TWINE?=$(PY) -m twine

BASEDIR=$(CURDIR)
OUTPUTDIR=$(BASEDIR)/dist
BUILDDIR=$(BASEDIR)/build

TEST_URL=light

help:
	@echo 'Makefile for packaging pyedgar '
	@echo ' '
	@echo 'Usage: '
	@echo '   make dist          (re)generate the build '
	@echo '   make upload_test   Upload the built distribution files to the test PyPi server'
	@echo '   make upload        Upload the built distribution files to the PyPi server '
	@echo '   make clean         Delete the setuptools folders and files '

dist:
	$(PY) setup.py sdist bdist_wheel

upload_test: dist
	$(TWINE) check dist/*
	$(TWINE) upload --repository-url https://test.pypi.org/legacy/ dist/*

upload: dist
	$(TWINE) check dist/*
	$(TWINE) upload dist/*

clean:
	[ ! -d $(OUTPUTDIR) ] || rm -rf $(OUTPUTDIR)
	[ ! -d $(BUILDDIR) ] || rm -rf $(BUILDDIR)


# echo '   example args [PORT=8000]'
# example:
# ifdef PORT
# 	$(PY) --version $(PORT)
# else
# 	$(PY) --version
# endif

.PHONY: help clean dist upload upload_test
