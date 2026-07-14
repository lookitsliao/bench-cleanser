"use strict";

function normalizeUsername(value) {
  if (typeof value !== "string") {
    throw new TypeError("value must be a string");
  }
  return value.toLowerCase();
}

module.exports = { normalizeUsername };
