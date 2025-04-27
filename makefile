
all: layout-preview.svg layout.svg \
     impl/zmk-keymap/ichnite.keymap \
     impl/zmk-keymap/ichnite-3x5_3.keymap \
     impl/zmk-keymap/ichnite-4x12.keymap \
     impl/qmk-layout/generated.h \
     impl/qmk-layout/generated-3x5_3.h


layout-preview.svg: readme.md
	python3 render_svg.py $< $@ --layers=base,SYM,NAV,NUM,SYS,FUN

layout.svg: readme.md
	python3 render_svg.py $< $@ --layers=base,SYM,NAV,NUM,SYS,FUN,UTF,FW,MOU,KP

impl/zmk-keymap/ichnite.keymap: readme.md
	@mkdir -p $(@D)
	python3 generate.py ZMK --transform=ichnite_transform $< $@

impl/zmk-keymap/ichnite-3x5_3.keymap: readme.md
	@mkdir -p $(@D)
	python3 generate.py --reshape=split3x5+3 ZMK --transform=split_3x5_3_transform $< $@

impl/zmk-keymap/ichnite-4x12.keymap: readme.md
	@mkdir -p $(@D)
	python3 generate.py --reshape=ortho4x12 ZMK --transform=ortho4x12_transform $< $@


impl/qmk-layout/generated.h: readme.md
	@mkdir -p $(@D)
	python3 generate.py QMK $< $@

impl/qmk-layout/generated-3x5_3.h: readme.md
	@mkdir -p $(@D)
	python3 generate.py --reshape=split3x5+3 QMK --layout=LAYOUT_split_3x5_3 $< $@
