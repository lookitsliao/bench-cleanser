"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { normalizeUsername } = require("./solution.js");

test("normalizes ASCII case", () => {
  assert.equal(normalizeUsername("ALICE"), "alice");
});

test("trims surrounding whitespace", () => {
  assert.equal(normalizeUsername("  Alice\t"), "alice");
});
