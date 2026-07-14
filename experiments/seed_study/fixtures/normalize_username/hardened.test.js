"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { normalizeUsername } = require("./solution.js");

test("preserves the complete stated behavior", () => {
  assert.equal(normalizeUsername("ALICE"), "alice");
  assert.equal(normalizeUsername("  Alice\t"), "alice");
  assert.equal(normalizeUsername(""), "");
  assert.throws(() => normalizeUsername(42), TypeError);
  assert.throws(() => normalizeUsername(null), TypeError);
});
