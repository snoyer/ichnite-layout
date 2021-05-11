
/**

const uint16_t PROGMEM shifty_shifts[][2] = {
	{KC_SLSH, KC_BSLS},
	{KC_DOT , KC_QUES},
	{KC_COMM, KC_SCLN},
};

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
	// ...
	SHIFTY_SHIFTS(get_highest_layer(layer_state)==0)
	// ...
}

*/



#include "matrix.h"

inline bool matrix_any(void) {
    for(uint8_t i=0; i<MATRIX_ROWS; ++i)
        if(matrix_get_row(i))
            return true;
    return false;
}




const uint16_t shifty_shifts_count = sizeof(shifty_shifts) / sizeof(uint16_t) / 2;
bool shifty_LSFT_state = false;


inline void reg_or_unreg_LSFT(const bool b) {
	if(b)  register_code(KC_LSFT);
	else unregister_code(KC_LSFT);
}

inline bool is_shifted(const uint16_t kc){
	return ((kc & 0xff00) & QK_LSFT);
}



inline void shifty_track_state(const keyrecord_t *record) {
	if(!matrix_any()) {
		unregister_code(KC_LSFT);
		shifty_LSFT_state = false;
	} else if(get_mods() & MOD_BIT(KC_LSFT)) {
		if(record->event.pressed) {
			shifty_LSFT_state = true;
		} else {
			if(!get_mods())
				unregister_code(KC_LSFT);
			shifty_LSFT_state = false;
		}
	}
}



inline bool shifty_hijack(const uint16_t kc1, const uint16_t kc2, const keyrecord_t *record) {
	if(record->event.pressed) {
		if(shifty_LSFT_state) {
			reg_or_unreg_LSFT(is_shifted(kc2));
			unregister_code(kc2 & 0xff);
			  register_code(kc2 & 0xff);
		} else {
			reg_or_unreg_LSFT(is_shifted(kc1));
			unregister_code(kc1 & 0xff);
		}
	} else {
		unregister_code(kc1 & 0xff);
		unregister_code(kc2 & 0xff);
		if(is_shifted(kc1) || !is_shifted(kc2))
			reg_or_unreg_LSFT(shifty_LSFT_state);
	};

	return shifty_LSFT_state;
}



bool shifty_process(const uint16_t keycode, const keyrecord_t *record, const bool do_hijack) {
	shifty_track_state(record);

	if(do_hijack) {
		for(uint16_t i=0; i<shifty_shifts_count; ++i) {
			const uint16_t normal = pgm_read_word(&shifty_shifts[i][0]);
			if((keycode & 0xff) == (normal & 0xff)) {
				const uint16_t shifted = pgm_read_word(&shifty_shifts[i][1]);
				if(shifty_hijack(normal, shifted, record))
					return true;
			}
		}
	}

	return false;
}

#define SHIFTY_SHIFTS(do_hijack) { \
	if(shifty_process(keycode, record, do_hijack)) \
		return false; \
}
