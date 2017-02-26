BUILDUI=../utils/buildui.py -5

UIC_SOURCE_FILES=$(wildcard adhoc_browser/ui/*.ui)
UIC_PYTHON_FILES=$(patsubst %.ui,%.py,$(UIC_SOURCE_FILES))

all: $(UIC_PYTHON_FILES)

clean:
	rm -rf $(UIC_PYTHON_FILES)

$(UIC_PYTHON_FILES): %.py: %.ui
	$(BUILDUI) $< $@
