"use strict";

function normalizeUsername(value) {
  if (typeof value !== "string") {
    throw new TypeError("value must be a string");
  }
  return value.trim().toLowerCase();
}

module.exports = { normalizeUsername };
