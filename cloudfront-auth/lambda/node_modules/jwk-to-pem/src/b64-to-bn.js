'use strict';

var BN = require('asn1.js').bignum,
	Buffer = require('safe-buffer').Buffer;

module.exports = function base64ToBigNum(val, zero) {
	var buf = Buffer.from(val, 'base64');
	var bn = val = new BN(buf, 10, 'be').iabs();
	if (zero) {
		buf.fill(0);
	}
	return bn;
};
