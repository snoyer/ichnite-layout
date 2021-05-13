#include QMK_KEYBOARD_H


#include "generated.h"
#include "shifty.h"

uint16_t custom_kc(const uint16_t keycode) {
	const bool is_osx = get_unicode_input_mode() == UC_OSX;

	switch(keycode) {
		case _COPY : return is_osx ? G(KC_C) : C(KC_C);
		case _CUT  : return is_osx ? G(KC_X) : C(KC_X);
		case _PASTE: return is_osx ? G(KC_V) : C(KC_V);

		case _UNDO : return is_osx ?   G(KC_Z)  :   C(KC_Z) ;
		case _REDO : return is_osx ? S(G(KC_Z)) : S(C(KC_Z));

		case _FINDNEXT : return is_osx ?   G(KC_G)  :   KC_F3 ;
		case _FINDPREV : return is_osx ? S(G(KC_G)) : S(KC_F3);
	}

	return 0;
}

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
	SHIFTY_SHIFTS(!get_highest_layer(layer_state))

	if(record->event.pressed) {
		const uint16_t custom = custom_kc(keycode);
		if(custom)
			tap_code16(custom);
	}

	return true;
}