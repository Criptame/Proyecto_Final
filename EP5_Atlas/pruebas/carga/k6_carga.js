// TC-NFR-03 · NFR-PERF-3: 200 usuarios concurrentes sobre el listado de clientes.
// Ejecución: docker run --rm -v <carga>:/scripts -v <reportes>:/out -e API=... -e TOKEN=... grafana/k6
//            run --summary-export=/out/k6_resumen.json /scripts/k6_carga.js
import http from 'k6/http';
import { check } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 200 }, // rampa
    { duration: '60s', target: 200 }, // carga sostenida
    { duration: '10s', target: 0 },   // descenso
  ],
  thresholds: {
    http_req_duration: ['p(95)<300'], // NFR-PERF-1 / NFR-PERF-3
    http_req_failed: ['rate<0.01'],
  },
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)'],
};

export default function () {
  const r = http.get(`${__ENV.API}/clientes`, {
    headers: { Authorization: `Bearer ${__ENV.TOKEN}` },
    timeout: '30s',
  });
  check(r, { 'HTTP 200': (x) => x.status === 200 });
}
