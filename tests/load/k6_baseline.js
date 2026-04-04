import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 50, // 50 concurrent users
  duration: "30s",
};

const BASE_URL = "http://localhost:8000";

export default function () {
  // Test 1: Health check
  const health = http.get(`${BASE_URL}/health`);
  check(health, {
    "health status 200": (r) => r.status === 200,
  });

  // Test 2: Shorten a URL
  const payload = JSON.stringify({ url: "https://google.com" });
  const params = { headers: { "Content-Type": "application/json" } };
  const shorten = http.post(`${BASE_URL}/shorten`, payload, params);
  check(shorten, {
    "shorten status 201": (r) => r.status === 201,
  });

  // Test 3: Redirect
  if (shorten.status === 201) {
    const short_code = JSON.parse(shorten.body).short_code;
    const redirect = http.get(`${BASE_URL}/${short_code}`, {
      redirects: 0,
    });
    check(redirect, {
      "redirect status 302": (r) => r.status === 302,
    });
  }

  sleep(1);
}
