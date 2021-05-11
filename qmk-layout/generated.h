// generated from `../readme.md`

enum layers {
	base=0, SYM, NUM, FUN, NAV, SYS, MWH, NUM_NAV, NUM_FUN
};
enum custom_keys {
	_FINDPREV=SAFE_RANGE, _CUT, _FINDNEXT, _COPY, _PASTE, _UNDO, _REDO
};
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
	[base] = LAYOUT_split_3x5_3(
		KC_Q          , KC_W          , KC_F          , KC_P           , KC_B          , KC_J          , KC_L        , KC_U        , KC_Y        , KC_QUOT     ,
		LGUI_T(KC_A)  , LALT_T(KC_R)  , LCTL_T(KC_S)  , LSFT_T(KC_T)   , KC_G          , KC_M          , LSFT_T(KC_N), LCTL_T(KC_E), LALT_T(KC_I), LGUI_T(KC_O),
		KC_Z          , KC_X          , KC_C          , KC_D           , KC_V          , KC_K          , KC_H        , KC_COMM     , KC_DOT      , KC_SLSH     ,
		LT(MWH,KC_ESC), LT(NAV,KC_SPC), LT(SYS,KC_TAB), LT(NUM,KC_BSPC), LT(SYM,KC_ENT), LT(FUN,KC_DEL)
	),
	[SYM] = LAYOUT_split_3x5_3(
		KC_TILD , KC_DLR  , KC_AT   , KC_LBRC , KC_RBRC , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_GRV  ,
		KC_HASH , KC_CIRC , KC_AMPR , KC_LPRN , KC_RPRN , KC_NO   , KC_LSFT , KC_LCTL , KC_LALT , KC_LGUI ,
		KC_ASTR , KC_NO   , KC_PERC , KC_LCBR , KC_RCBR , KC_NO   , KC_NO   , KC_COLN , KC_EXLM , KC_PIPE ,
		KC_PLUS , KC_UNDS , KC_EQL  , KC_NO   , KC_NO   , KC_NO   
	),
	[NUM] = LAYOUT_split_3x5_3(
		KC_1    , KC_2               , KC_3    , KC_4    , KC_5    , KC_6       , KC_7    , KC_8    , KC_9    , KC_0    ,
		KC_LGUI , KC_LALT            , KC_LCTL , KC_LSFT , KC_NO   , KC_MINS    , KC_4    , KC_5    , KC_6    , KC_DOT  ,
		KC_ASTR , KC_NO              , KC_NO   , KC_LT   , KC_GT   , KC_0       , KC_1    , KC_2    , KC_3    , KC_SLSH ,
		KC_PLUS , LT(NUM_NAV,KC_MINS), KC_EQL  , KC_NO   , KC_NO   , MO(NUM_FUN)
	),
	[FUN] = LAYOUT_split_3x5_3(
		KC_F1   , KC_F2   , KC_F3   , KC_F4   , KC_F5   , KC_F6   , KC_F7   , KC_F8   , KC_F9   , KC_F10  ,
		KC_LGUI , KC_LALT , KC_LCTL , KC_LSFT , KC_NO   , KC_PSCR , KC_F4   , KC_F5   , KC_F6   , KC_F11  ,
		KC_NO   , KC_NO   , KC_INS  , KC_SLCK , KC_PAUS , KC_NO   , KC_F1   , KC_F2   , KC_F3   , KC_F12  ,
		KC_NO   , KC_APP  , KC_NO   , KC_NO   , KC_NO   , KC_NO   
	),
	[NAV] = LAYOUT_split_3x5_3(
		_FINDPREV, KC_HOME , KC_UP   , KC_END   , _CUT    , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   ,
		_FINDNEXT, KC_LEFT , KC_DOWN , KC_RIGHT , _COPY   , KC_NO   , KC_LSFT , KC_LCTL , KC_LALT , KC_LGUI ,
		KC_NO    , KC_PGUP , KC_NO   , KC_PGDOWN, _PASTE  , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   ,
		KC_NO    , KC_NO   , KC_NO   , _UNDO    , KC_NO   , _REDO   
	),
	[SYS] = LAYOUT_split_3x5_3(
		KC_BRIU , KC_MRWD , KC_VOLU , KC_MFFD , KC_MYCM , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   ,
		KC_BRID , KC_MSTP , KC_VOLD , KC_MPLY , KC_WHOM , KC_NO   , KC_LSFT , KC_LCTL , KC_LALT , KC_LGUI ,
		KC_NO   , KC_MPRV , KC_MUTE , KC_MNXT , KC_CALC , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   ,
		KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   
	),
	[MWH] = LAYOUT_split_3x5_3(
		KC_NO   , KC_NO   , KC_WH_U , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   ,
		KC_NO   , KC_WH_L , KC_WH_D , KC_WH_R , KC_NO   , KC_NO   , KC_LSFT , KC_LCTL , KC_LALT , KC_LGUI ,
		KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   ,
		KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   
	),
	[NUM_NAV] = LAYOUT_split_3x5_3(
		KC_NO     , UC(0x20ac), UC(0x00b0), KC_NO     , KC_NO     , KC_NO   , UC(0x0394), UC(0x03b5), UC(0x03bc), KC_NO   ,
		UC(0x221e), UC(0x00d7), UC(0x221a), UC(0x00b2), UC(0x00b3), KC_NO   , UC(0x03b1), UC(0x03b2), UC(0x03bb), KC_NO   ,
		UC(0x00b1), UC(0x2260), UC(0x2248), UC(0x2264), UC(0x2265), KC_NO   , UC(0x03c6), UC(0x03b8), UC(0x03c0), KC_NO   ,
		KC_NO     , KC_NO     , KC_NO     , KC_NO     , KC_NO     , KC_NO   
	),
	[NUM_FUN] = LAYOUT_split_3x5_3(
		RESET   , KC_NO   , KC_NO   , KC_NO   , UC_M_MA , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   ,
		DEBUG   , KC_NO   , KC_NO   , KC_NO   , UC_M_LN , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   ,
		KC_NO   , KC_NO   , KC_NO   , KC_NO   , UC_M_WI , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   ,
		KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   , KC_NO   
	)
};
const uint16_t PROGMEM shifty_shifts[][2] = {
	{ KC_QUOT , KC_DQUO  },
	{ KC_COMM , KC_SCLN  },
	{ KC_DOT  , KC_QUES  },
	{ KC_SLSH , KC_BSLS  },
	{ KC_SPC  , KC_MINS  }
};
