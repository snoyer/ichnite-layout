#include QMK_KEYBOARD_H

#include "generated-3x5_3.h"

layer_state_t layer_state_set_user(layer_state_t state) {
	change_os_mode_for_base_layer(state);
	return state;
}
