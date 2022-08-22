

enum td_keycodes {
	LT_UTF_LCTL_Z,
	LT_UTF_LGUI_Z
};



enum layers {
	BASE_l = 0,
	BASE_m = 1,
	BASE_w = 2,
	SYM = 3,
	NUM = 4,
	KP = 5,
	FUN = 6,
	NAV_lw = 7,
	NAV_m = 8,
	SYS = 9,
	MWH = 10,
	UTF = 11,
	FW = 12
};

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
	/* Colemak-DHm `base` layer
	┌────────┬────────┬──────────┬────────────┬──────────┐  ┌────────────┬───────────┬──────────┬────────┬────────┐
	│   q    │   w    │    f     │     p      │    b     │  │     j      │     l     │    u     │   y    │  '"    │
	├────────┼────────┼──────────┼────────────┼──────────┤  ├────────────┼───────────┼──────────┼────────┼────────┤
	│ a ⇩CMD │ r ⇩ALT │ s ⇩CTRL  │  t ⇩SHIFT  │    g     │  │     m      │ n ⇩SHIFT  │ e ⇩CTRL  │ i ⇩ALT │ o ⇩CMD │
	├────────┼────────┼──────────┼────────────┼──────────┤  ├────────────┼───────────┼──────────┼────────┼────────┤
	│   z    │   x    │    c     │     d      │    v     │  │     k      │     h     │   ,;     │  .?    │  /\    │
	└────────┴────────┼──────────┼────────────┼──────────┤  ├────────────┼───────────┼──────────┼────────┴────────┘
	                  │ ESC ⇩MWH │ SPACE ⇩NAV │ TAB ⇩SYS │  │ ENTER ⇩NUM │ BSPC ⇩SYM │ DEL ⇩FUN │                  
	                  └──────────┴────────────┴──────────┘  └────────────┴───────────┴──────────┘                   */
	[BASE_l] = LAYOUT_split_3x5_3(
		 KC_Q,         KC_W,         KC_F,           KC_P,              KC_B,            KC_J,           KC_L,            KC_U,           KC_Y,         KC_QUOT,
		 LGUI_T(KC_A), LALT_T(KC_R), LCTL_T(KC_S),   LSFT_T(KC_T),      KC_G,            KC_M,           LSFT_T(KC_N),    LCTL_T(KC_E),   LALT_T(KC_I), LGUI_T(KC_O),
		 KC_Z,         KC_X,         KC_C,           KC_D,              KC_V,            KC_K,           KC_H,            KC_COMM,        KC_DOT,       KC_SLSH,
		                             LT(MWH,KC_ESC), LT(NAV_lw,KC_SPC), LT(SYS,KC_TAB),  LT(NUM,KC_ENT), LT(SYM,KC_BSPC), LT(FUN,KC_DEL)
	),
	[BASE_m] = LAYOUT_split_3x5_3(
		 KC_Q,         KC_W,         KC_F,           KC_P,             KC_B,            KC_J,           KC_L,            KC_U,           KC_Y,         KC_QUOT,
		 LGUI_T(KC_A), LALT_T(KC_R), LCTL_T(KC_S),   LSFT_T(KC_T),     KC_G,            KC_M,           LSFT_T(KC_N),    LCTL_T(KC_E),   LALT_T(KC_I), LGUI_T(KC_O),
		 KC_Z,         KC_X,         KC_C,           KC_D,             KC_V,            KC_K,           KC_H,            KC_COMM,        KC_DOT,       KC_SLSH,
		                             LT(MWH,KC_ESC), LT(NAV_m,KC_SPC), LT(SYS,KC_TAB),  LT(NUM,KC_ENT), LT(SYM,KC_BSPC), LT(FUN,KC_DEL)
	),
	[BASE_w] = LAYOUT_split_3x5_3(
		 KC_Q,         KC_W,         KC_F,           KC_P,              KC_B,            KC_J,           KC_L,            KC_U,           KC_Y,         KC_QUOT,
		 LGUI_T(KC_A), LALT_T(KC_R), LCTL_T(KC_S),   LSFT_T(KC_T),      KC_G,            KC_M,           LSFT_T(KC_N),    LCTL_T(KC_E),   LALT_T(KC_I), LGUI_T(KC_O),
		 KC_Z,         KC_X,         KC_C,           KC_D,              KC_V,            KC_K,           KC_H,            KC_COMM,        KC_DOT,       KC_SLSH,
		                             LT(MWH,KC_ESC), LT(NAV_lw,KC_SPC), LT(SYS,KC_TAB),  LT(NUM,KC_ENT), LT(SYM,KC_BSPC), LT(FUN,KC_DEL)
	),
	/* Symbols
	┌───────┬───────┬───────┬───────┬───────┐  ┌───────┬───────┬───────┬───────┬───────┐
	│   ~   │   ^   │   &   │   [   │   ]   │  │       │       │       │       │   `   │
	├───────┼───────┼───────┼───────┼───────┤  ├───────┼───────┼───────┼───────┼───────┤
	│   #   │   $   │   @   │   (   │   )   │  │       │ SHIFT │ CTRL  │  ALT  │  CMD  │
	├───────┼───────┼───────┼───────┼───────┤  ├───────┼───────┼───────┼───────┼───────┤
	│   *   │       │   %   │   {   │   }   │  │       │       │   :   │   !   │ PIPE  │
	└───────┴───────┼───────┼───────┼───────┤  ├───────┼───────┼───────┼───────┴───────┘
	                │   +   │   _   │   =   │  │  ⇩KP  │       │       │                
	                └───────┴───────┴───────┘  └───────┴───────┴───────┘                 */
	[SYM] = LAYOUT_split_3x5_3(
		 KC_TILD, KC_CIRC, KC_AMPR, KC_LBRC, KC_RBRC,  KC_NO,  KC_NO,   KC_NO,   KC_NO,   KC_GRV,
		 KC_HASH, KC_DLR,  KC_AT,   KC_LPRN, KC_RPRN,  KC_NO,  KC_LSFT, KC_LCTL, KC_LALT, KC_LGUI,
		 KC_ASTR, KC_NO,   KC_PERC, KC_LCBR, KC_RCBR,  KC_NO,  KC_NO,   KC_COLN, KC_EXLM, KC_PIPE,
		                   KC_PLUS, KC_UNDS, KC_EQL,   MO(KP), KC_NO,   KC_NO
	),
	/* Numerals
	┌───────┬───────┬───────┬───────┬───────┐  ┌───────┬───────┬───────────┬───────┬───────┐
	│   1   │   2   │   3   │   4   │   5   │  │   6   │   7   │     8     │   9   │   0   │
	├───────┼───────┼───────┼───────┼───────┤  ├───────┼───────┼───────────┼───────┼───────┤
	│  CMD  │  ALT  │ CTRL  │ SHIFT │       │  │   -   │   4   │     5     │   6   │   .   │
	├───────┼───────┼───────┼───────┼───────┤  ├───────┼───────┼───────────┼───────┼───────┤
	│   *   │       │   %   │   <   │   >   │  │   0   │   1   │     2     │   3   │   /   │
	└───────┴───────┼───────┼───────┼───────┤  ├───────┼───────┼───────────┼───────┴───────┘
	                │   +   │   -   │   =   │  │       │  ⇩KP  │ NLOCK ⇩FW │                
	                └───────┴───────┴───────┘  └───────┴───────┴───────────┘                 */
	[NUM] = LAYOUT_split_3x5_3(
		 KC_1,    KC_2,    KC_3,    KC_4,    KC_5,    KC_6,    KC_7,   KC_8,           KC_9, KC_0,
		 KC_LGUI, KC_LALT, KC_LCTL, KC_LSFT, KC_NO,   KC_MINS, KC_4,   KC_5,           KC_6, KC_DOT,
		 KC_ASTR, KC_NO,   KC_PERC, KC_LT,   KC_GT,   KC_0,    KC_1,   KC_2,           KC_3, KC_SLSH,
		                   KC_PLUS, KC_MINS, KC_EQL,  KC_NO,   MO(KP), LT(FW,KC_NLCK)
	),
	/* Keypad numerals on `NUM+SYM` combo
	┌───────┬───────┬───────┬───────┬───────┐  ┌───────┬───────┬───────┬───────┬───────┐
	│  KP1  │  KP2  │  KP3  │  KP4  │  KP5  │  │  KP6  │  KP7  │  KP8  │  KP9  │  KP0  │
	├───────┼───────┼───────┼───────┼───────┤  ├───────┼───────┼───────┼───────┼───────┤
	│  CMD  │  ALT  │ CTRL  │ SHIFT │       │  │  KP-  │  KP4  │  KP5  │  KP6  │  KP.  │
	├───────┼───────┼───────┼───────┼───────┤  ├───────┼───────┼───────┼───────┼───────┤
	│  KP*  │       │   %   │   <   │   >   │  │  KP0  │  KP1  │  KP2  │  KP3  │  KP/  │
	└───────┴───────┼───────┼───────┼───────┤  ├───────┼───────┼───────┼───────┴───────┘
	                │  KP+  │  KP-  │  KP=  │  │       │       │       │                
	                └───────┴───────┴───────┘  └───────┴───────┴───────┘                 */
	[KP] = LAYOUT_split_3x5_3(
		 KC_P1,   KC_P2,   KC_P3,   KC_P4,   KC_P5,    KC_P6,   KC_P7, KC_P8, KC_P9, KC_P0,
		 KC_LGUI, KC_LALT, KC_LCTL, KC_LSFT, KC_NO,    KC_PMNS, KC_P4, KC_P5, KC_P6, KC_PDOT,
		 KC_PAST, KC_NO,   KC_PERC, KC_LT,   KC_GT,    KC_P0,   KC_P1, KC_P2, KC_P3, KC_PSLS,
		                   KC_PPLS, KC_PMNS, KC_PEQL,  KC_NO,   KC_NO, KC_NO
	),
	/* Function keys
	┌───────┬───────┬───────┬───────┬───────┐  ┌───────┬───────┬───────┬───────┬───────┐
	│  F1   │  F2   │  F3   │  F4   │  F5   │  │  F6   │  F7   │  F8   │  F9   │  F10  │
	├───────┼───────┼───────┼───────┼───────┤  ├───────┼───────┼───────┼───────┼───────┤
	│  CMD  │  ALT  │ CTRL  │ SHIFT │ CAPS  │  │ PSCR  │  F4   │  F5   │  F6   │  F11  │
	├───────┼───────┼───────┼───────┼───────┤  ├───────┼───────┼───────┼───────┼───────┤
	│       │ PSCR  │ SLOCK │ PAUSE │  INS  │  │       │  F1   │  F2   │  F3   │  F12  │
	└───────┴───────┼───────┼───────┼───────┤  ├───────┼───────┼───────┼───────┴───────┘
	                │ rCTRL │  APP  │       │  │  ⇩FW  │       │       │                
	                └───────┴───────┴───────┘  └───────┴───────┴───────┘                 */
	[FUN] = LAYOUT_split_3x5_3(
		 KC_F1,   KC_F2,   KC_F3,   KC_F4,   KC_F5,    KC_F6,   KC_F7, KC_F8, KC_F9, KC_F10,
		 KC_LGUI, KC_LALT, KC_LCTL, KC_LSFT, KC_CLCK,  KC_PSCR, KC_F4, KC_F5, KC_F6, KC_F11,
		 KC_NO,   KC_PSCR, KC_SLCK, KC_BRK,  KC_INS,   KC_NO,   KC_F1, KC_F2, KC_F3, KC_F12,
		                   KC_RCTL, KC_APP,  KC_NO,    MO(FW),  KC_NO, KC_NO
	),
	/* Navigation
	┌───────┬───────┬───────┬───────┬───────┐  ┌───────┬───────────┬───────┬───────┬───────┐
	│ FIND- │ HOME  │  UP   │  END  │  CUT  │  │       │           │       │       │   "   │
	├───────┼───────┼───────┼───────┼───────┤  ├───────┼───────────┼───────┼───────┼───────┤
	│ FIND+ │ LEFT  │ DOWN  │ RIGHT │ COPY  │  │       │   SHIFT   │ CTRL  │  ALT  │  CMD  │
	├───────┼───────┼───────┼───────┼───────┤  ├───────┼───────────┼───────┼───────┼───────┤
	│ ENTER │ PG_UP │       │ PG_DN │ PASTE │  │       │           │   ;   │   ?   │   \   │
	└───────┴───────┼───────┼───────┼───────┤  ├───────┼───────────┼───────┼───────┴───────┘
	                │       │       │       │  │ REDO  │ UNDO ⇩UTF │       │                
	                └───────┴───────┴───────┘  └───────┴───────────┴───────┘                 */
	[NAV_lw] = LAYOUT_split_3x5_3(
		 LSFT(KC_F3), KC_HOME, KC_UP,   KC_END,  LCTL(KC_X),  KC_NO,      KC_NO,             KC_NO,   KC_NO,   KC_DQT,
		 KC_F3,       KC_LEFT, KC_DOWN, KC_RGHT, LCTL(KC_C),  KC_NO,      KC_LSFT,           KC_LCTL, KC_LALT, KC_LGUI,
		 KC_ENT,      KC_PGUP, KC_NO,   KC_PGDN, LCTL(KC_V),  KC_NO,      KC_NO,             KC_SCLN, KC_QUES, KC_BSLS,
		                       KC_NO,   KC_NO,   KC_NO,       LCTL(KC_Y), TD(LT_UTF_LCTL_Z), KC_NO
	),
	[NAV_m] = LAYOUT_split_3x5_3(
		 LSFT(LGUI(KC_G)), KC_HOME, KC_UP,   KC_END,  LGUI(KC_X),  KC_NO,      KC_NO,             KC_NO,   KC_NO,   KC_DQT,
		 LGUI(KC_G),       KC_LEFT, KC_DOWN, KC_RGHT, LGUI(KC_C),  KC_NO,      KC_LSFT,           KC_LCTL, KC_LALT, KC_LGUI,
		 KC_ENT,           KC_PGUP, KC_NO,   KC_PGDN, LGUI(KC_V),  KC_NO,      KC_NO,             KC_SCLN, KC_QUES, KC_BSLS,
		                            KC_NO,   KC_NO,   KC_NO,       LGUI(KC_Y), TD(LT_UTF_LGUI_Z), KC_NO
	),
	/* System/media keys
	┌───────┬───────┬───────┬───────┬────────┐  ┌───────┬───────┬───────┬───────┬───────┐
	│ BRI+  │  RWD  │ VOL+  │  FFW  │  WWW   │  │       │       │       │       │       │
	├───────┼───────┼───────┼───────┼────────┤  ├───────┼───────┼───────┼───────┼───────┤
	│ BRI-  │ STOP  │ VOL-  │ PLAY  │ MYCOMP │  │       │ SHIFT │ CTRL  │  ALT  │  CMD  │
	├───────┼───────┼───────┼───────┼────────┤  ├───────┼───────┼───────┼───────┼───────┤
	│       │ PREV  │ MUTE  │ NEXT  │ CALC   │  │       │       │       │       │       │
	└───────┴───────┼───────┼───────┼────────┤  ├───────┼───────┼───────┼───────┴───────┘
	                │  ⇩FW  │       │        │  │       │       │       │                
	                └───────┴───────┴────────┘  └───────┴───────┴───────┘                 */
	[SYS] = LAYOUT_split_3x5_3(
		 KC_BRIU, KC_MRWD, KC_VOLU, KC_MFFD, KC_WHOM,  KC_NO, KC_NO,   KC_NO,   KC_NO,   KC_NO,
		 KC_BRID, KC_MSTP, KC_VOLD, KC_MPLY, KC_MYCM,  KC_NO, KC_LSFT, KC_LCTL, KC_LALT, KC_LGUI,
		 KC_NO,   KC_MPRV, KC_MUTE, KC_MNXT, KC_CALC,  KC_NO, KC_NO,   KC_NO,   KC_NO,   KC_NO,
		                   MO(FW),  KC_NO,   KC_NO,    KC_NO, KC_NO,   KC_NO
	),
	/* Mouse scrolling
	┌───────┬───────┬───────┬───────┬───────┐  ┌───────┬───────┬───────┬───────┬───────┐
	│       │       │ WH_U  │       │       │  │       │       │       │       │       │
	├───────┼───────┼───────┼───────┼───────┤  ├───────┼───────┼───────┼───────┼───────┤
	│       │ WH_L  │ WH_D  │ WH_R  │       │  │       │ SHIFT │ CTRL  │  ALT  │  CMD  │
	├───────┼───────┼───────┼───────┼───────┤  ├───────┼───────┼───────┼───────┼───────┤
	│       │       │       │       │       │  │       │       │       │       │       │
	└───────┴───────┼───────┼───────┼───────┤  ├───────┼───────┼───────┼───────┴───────┘
	                │       │       │  ⇩FW  │  │       │       │       │                
	                └───────┴───────┴───────┘  └───────┴───────┴───────┘                 */
	[MWH] = LAYOUT_split_3x5_3(
		 KC_NO, KC_NO,   KC_WH_U, KC_NO,   KC_NO,   KC_NO, KC_NO,   KC_NO,   KC_NO,   KC_NO,
		 KC_NO, KC_WH_L, KC_WH_D, KC_WH_R, KC_NO,   KC_NO, KC_LSFT, KC_LCTL, KC_LALT, KC_LGUI,
		 KC_NO, KC_NO,   KC_NO,   KC_NO,   KC_NO,   KC_NO, KC_NO,   KC_NO,   KC_NO,   KC_NO,
		                 KC_NO,   KC_NO,   MO(FW),  KC_NO, KC_NO,   KC_NO
	),
	/* Unicode Symbols on `NAV>SYM`
	┌───────┬───────┬───────┬───────┬───────┐  ┌───────┬───────┬───────┬───────┬───────┐
	│       │       │   °   │   √   │       │  │       │   μ   │   Δ   │   ε   │       │
	├───────┼───────┼───────┼───────┼───────┤  ├───────┼───────┼───────┼───────┼───────┤
	│   ∞   │   €   │       │   ²   │   ³   │  │       │   π   │   φ   │   θ   │       │
	├───────┼───────┼───────┼───────┼───────┤  ├───────┼───────┼───────┼───────┼───────┤
	│   ×   │       │   ≈   │   ≤   │   ≥   │  │   λ   │   α   │   β   │   ¿   │   ÷   │
	└───────┴───────┼───────┼───────┼───────┤  ├───────┼───────┼───────┼───────┴───────┘
	                │   ±   │       │   ≠   │  │       │       │       │                
	                └───────┴───────┴───────┘  └───────┴───────┴───────┘                 */
	[UTF] = LAYOUT_split_3x5_3(
		 KC_NO,      KC_NO,      UC(0x00b0), UC(0x221a), KC_NO,       KC_NO,      UC(0x03bc), UC(0x0394), UC(0x03b5), KC_NO,
		 UC(0x221e), UC(0x20ac), KC_NO,      UC(0x00b2), UC(0x00b3),  KC_NO,      UC(0x03c0), UC(0x03c6), UC(0x03b8), KC_NO,
		 UC(0x00d7), KC_NO,      UC(0x2248), UC(0x2264), UC(0x2265),  UC(0x03bb), UC(0x03b1), UC(0x03b2), UC(0x00bf), UC(0x00f7),
		                         UC(0x00b1), KC_NO,      UC(0x2260),  KC_NO,      KC_NO,      KC_NO
	),
	/* Firmware on `NUM+FUN` or `MWH+SYS` combo
	┌───────┬───────┬───────┬────────┬───────┐  ┌───────┬───────┬───────┬───────┬───────┐
	│  BT1  │  BT2  │  BT3  │  BT4   │  BT5  │  │  USB  │       │       │       │ BTCLR │
	├───────┼───────┼───────┼────────┼───────┤  ├───────┼───────┼───────┼───────┼───────┤
	│       │ @win  │ @mac  │ @linux │       │  │       │       │       │       │       │
	├───────┼───────┼───────┼────────┼───────┤  ├───────┼───────┼───────┼───────┼───────┤
	│       │       │       │        │       │  │       │       │       │       │       │
	└───────┴───────┼───────┼────────┼───────┤  ├───────┼───────┼───────┼───────┴───────┘
	                │ DEBUG │ RESET  │ BOOTL │  │ BOOTL │ RESET │ DEBUG │                
	                └───────┴────────┴───────┘  └───────┴───────┴───────┘                 */
	[FW] = LAYOUT_split_3x5_3(
		 KC_NO, KC_NO,      KC_NO,      KC_NO,      KC_NO,  KC_NO, KC_NO, KC_NO, KC_NO, KC_NO,
		 KC_NO, TO(BASE_w), TO(BASE_m), TO(BASE_l), KC_NO,  KC_NO, KC_NO, KC_NO, KC_NO, KC_NO,
		 KC_NO, KC_NO,      KC_NO,      KC_NO,      KC_NO,  KC_NO, KC_NO, KC_NO, KC_NO, KC_NO,
		                    DEBUG,      RESET,      RESET,  RESET, RESET, DEBUG
	)
};


/* needs to be called from `layer_state_set_user` in keymap code */
void change_os_mode_for_base_layer(layer_state_t state) {
	switch (get_highest_layer(state)) {
		case BASE_l: set_unicode_input_mode(UC_LNX); break;
		case BASE_m: set_unicode_input_mode(UC_OSX); break;
		case BASE_w: set_unicode_input_mode(UC_WIN); break;
	}
}





const key_override_t KC_COMM_KC_SCLN_shift_override = ko_make_basic(MOD_MASK_SHIFT, KC_COMM, KC_SCLN);
const key_override_t KC_DOT_KC_QUES_shift_override = ko_make_basic(MOD_MASK_SHIFT, KC_DOT, KC_QUES);
const key_override_t KC_QUOT_KC_DQUO_shift_override = ko_make_basic(MOD_MASK_SHIFT, KC_QUOT, KC_DQUO);
const key_override_t KC_SLSH_KC_BSLS_shift_override = ko_make_basic(MOD_MASK_SHIFT, KC_SLSH, KC_BSLS);

const key_override_t **key_overrides = (const key_override_t *[]){
	&KC_COMM_KC_SCLN_shift_override,
	&KC_DOT_KC_QUES_shift_override,
	&KC_QUOT_KC_DQUO_shift_override,
	&KC_SLSH_KC_BSLS_shift_override,
	NULL
};





typedef enum {
	TD_NONE,
	TD_UNKNOWN,
	TD_SINGLE_TAP,
	TD_SINGLE_HOLD,
	TD_DOUBLE_SINGLE_TAP
} td_state_t;

static td_state_t td_state;

td_state_t update_td_state(const qk_tap_dance_state_t *state){
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

void tapdance_TDLT_finished(qk_tap_dance_state_t *state, void *user_data){
	const tdlt_data *data = (tdlt_data*) user_data;
	switch(update_td_state(state)){
		case TD_SINGLE_TAP: register_code16(data->keycode); break;
		case TD_SINGLE_HOLD: layer_on(data->layer); break;
		case TD_DOUBLE_SINGLE_TAP: tap_code16(data->keycode); register_code16(data->keycode); break;
		default: break;
	}
}

void tapdance_TDLT_reset(qk_tap_dance_state_t *state, void *user_data){
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

qk_tap_dance_action_t tap_dance_actions[] = {
	[LT_UTF_LCTL_Z] = ACTION_TAP_DANCE_LT(UTF, LCTL(KC_Z)),
	[LT_UTF_LGUI_Z] = ACTION_TAP_DANCE_LT(UTF, LGUI(KC_Z))
};