"use strict";

// A tiny in-memory order service used as a DevPilot AI demo target.

const ORDERS = [
  { id: 1, item: "keyboard", qty: 2, status: "pending" },
  { id: 2, item: "mouse", qty: 1, status: "shipped" },
  { id: 3, item: "monitor", qty: 1, status: "pending" },
];

function findOrder(id) {
  return ORDERS.find((o) => o.id === id) || null;
}

function ordersByStatus(status) {
  return ORDERS.filter((o) => o.status === status);
}

function totalUnits() {
  return ORDERS.reduce((sum, o) => sum + o.qty, 0);
}

module.exports = { ORDERS, findOrder, ordersByStatus, totalUnits };
