SPHINXBUILD ?= sphinx-build-3

docs-html:
	cd docs; $(MAKE) SPHINXBUILD=$(SPHINXBUILD) html

docs-view-html: docs-html
	xdg-open docs/sphinx-data/build/html/index.html

.PHONY: docs-html
