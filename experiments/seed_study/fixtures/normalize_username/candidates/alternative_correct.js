"use strict";

const EDGE_WHITESPACE = /^\s+|\s+$/g;

function normalizeUsername(value) {
  if (typeof value !== "string") {
    throw new TypeError("expected string input");
  }
  return value.replace(EDGE_WHITESPACE, "").toLowerCase();
}

module.exports = { normalizeUsername };
