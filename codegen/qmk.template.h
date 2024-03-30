/*%- if custom_LTs -*/
enum td_keycodes {
/*%- for o in custom_LTs */
	/*= o.identifier */
	/*=- '' if loop.last else ',' */
/*%- endfor */
};
/*%- endif */


enum layers {
/*%- for name in layer_blocks.keys() */
	/*= name */ = /*= loop.index - 1 */
	/*=- '' if loop.last else ',' */
/*%- endfor */
};

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
/*%- filter indent('\t') */
/*= layer_blocks.values() |join(',\n') */
/*%- endfilter */
};


/* needs to be called from `layer_state_set_user` in keymap code */
void change_os_mode_for_base_layer(layer_state_t state) {
	/*%- if uc_modes */
	switch (get_highest_layer(state)) {
		/*%- for k,v in uc_modes */
		case /*= k */: set_unicode_input_mode(/*= v */); break;
		/*%- endfor */
	}
	/*%- endif */
}



/*%- if custom_shifts -*/

/*% for s in custom_shifts */
const key_override_t /*= s.normal */_/*= s.shifted */_shift_override = ko_make_basic(MOD_MASK_SHIFT, /*= s.normal */, /*= s.shifted */);
/*%- endfor */

const key_override_t **key_overrides = (const key_override_t *[]){
/*%- for s in custom_shifts */
	&/*= s.normal */_/*= s.shifted */_shift_override,
/*%- endfor */
	NULL
};

/*%- endif -*/




/*%- if custom_LTs */

typedef enum {
	TD_NONE,
	TD_UNKNOWN,
	TD_SINGLE_TAP,
	TD_SINGLE_HOLD,
	TD_DOUBLE_SINGLE_TAP
} td_state_t;

static td_state_t td_state;

td_state_t update_td_state(const tap_dance_state_t *state){
	if(state->count == 1)
		td_state = (state->interrupted || !state->pressed) ? TD_SINGLE_TAP : TD_SINGLE_HOLD;
	else
		td_state = (state->count == 2) ? TD_DOUBLE_SINGLE_TAP : TD_UNKNOWN;
	return td_state;
}


typedef struct {
  uint16_t layer;
  uint16_t keycode;
} tdlt_data;

void tapdance_TDLT_finished(tap_dance_state_t *state, void *user_data){
	const tdlt_data *data = (tdlt_data*) user_data;
	switch(update_td_state(state)){
		case TD_SINGLE_TAP: register_code16(data->keycode); break;
		case TD_SINGLE_HOLD: layer_on(data->layer); break;
		case TD_DOUBLE_SINGLE_TAP: tap_code16(data->keycode); register_code16(data->keycode); break;
		default: break;
	}
}

void tapdance_TDLT_reset(tap_dance_state_t *state, void *user_data){
	const tdlt_data *data = (tdlt_data*) user_data;
	switch(td_state){
		case TD_SINGLE_TAP: unregister_code16(data->keycode); break;
		case TD_SINGLE_HOLD: layer_off(data->layer); break;
		case TD_DOUBLE_SINGLE_TAP: unregister_code16(data->keycode);
		default: break;
	}
}

#define ACTION_TAP_DANCE_LT(layer, keycode) { \
	.fn = {NULL, tapdance_TDLT_finished, tapdance_TDLT_reset}, \
	.user_data = (void*)&((tdlt_data){ layer, keycode }), \
}

tap_dance_action_t tap_dance_actions[] = {
/*%- for lt in custom_LTs */
	[/*= lt.identifier */] = ACTION_TAP_DANCE_LT(/*= lt.layer */, /*= lt.keycode */)
	/*=- '' if loop.last else ',' */
/*%- endfor */
};

/*%- endif */
