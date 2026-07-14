"use strict";

function normalizeUsername(value) {
  return String(value).trim().toLowerCase();
}

module.exports = { normalizeUsername };
