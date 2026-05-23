"use strict";

const test = require("node:test");
const assert = require("node:assert");
const { findOrder, ordersByStatus, totalUnits } = require("../src/index.js");

test("findOrder returns a known order", () => {
  assert.strictEqual(findOrder(1).item, "keyboard");
});

test("findOrder returns null when missing", () => {
  assert.strictEqual(findOrder(999), null);
});

test("ordersByStatus filters correctly", () => {
  assert.strictEqual(ordersByStatus("pending").length, 2);
});

test("totalUnits sums quantities", () => {
  assert.strictEqual(totalUnits(), 4);
});
