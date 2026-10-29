import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { normalize, pickFiles, listAssets } from '../src/polyhaven.js';
import { search } from '../src/search.js';
import { sync, loadCatalog } from '../src/sync.js';

const chair = normalize('ArmChair_01', { name: 'Arm Chair 01', categories: ['furniture', 'seating'], tags: ['gothic', 'vintage', 'chair', 'wood'], authors: { 'Kirill Sannikov': 'All' }, polycount: 5626, dimensions: [848.4, 765.7, 1065.1], max_resolution: [4096, 4096], description: 'Free (CC0) vintage Victorian armchair 3D model', date_published: 1585605600, attributes: { condition: ['worn'], material: ['wood', 'fabric'] } }, 'model');
const dawn = normalize('aarfontein_dawn_2', { name: 'Aarfontein Dawn 2', categories: ['outdoor', 'natural light', 'sunrise-sunset'], tags: ['grass', 'blue hour', 'horizon glow'], authors: { 'Dario Barresi': 'All' }, max_resolution: [24576, 12288], description: 'Free, unclipped 24K HDRI of a rocky grassland at dawn', attributes: { time_of_day: 'sunrise' } }, 'hdri');
const asphalt = normalize('aerial_asphalt_01', { name: 'Aerial Asphalt 01', categories: ['asphalt', 'outdoor', 'floor', 'road'], tags: ['road', 'cracked'], authors: { 'Rob Tuytel': 'All' }, max_resolution: [8192, 8192], description: 'Free 8K asphalt texture of a worn road' }, 'texture');
const rows = [chair, dawn, asphalt];

test('an asset of the API becomes a line of the register: CC0, tags, size, authors, page', () => {
  assert.equal(chair.id, 'ph-ArmChair_01'); assert.equal(chair.kind, 'model'); assert.equal(chair.licence, 'cc0'); assert.equal(chair.polycount, 5626);
  assert.deepEqual(chair.dimensions, [848, 766, 1065]); assert.equal(chair.published, '2020-03-30'); assert.equal(chair.page, 'https://polyhaven.com/a/ArmChair_01');
  assert.ok(chair.attributes.includes('wood') && chair.attributes.includes('worn'));
});

test('search: a French brief finds the right kind of asset, the filters are exact', () => {
  assert.equal(search(rows, 'un vieux fauteuil en bois')[0].id, 'ph-ArmChair_01');
  assert.equal(search(rows, 'lumière du lever de soleil', { kind: 'hdri' })[0].id, 'ph-aarfontein_dawn_2');
  assert.equal(search(rows, 'route usée')[0].id, 'ph-aerial_asphalt_01');
  assert.deepEqual(search(rows, 'fauteuil', { maxPolycount: 1000 }), []);
  assert.deepEqual(search(rows, 'fauteuil', { kind: 'texture' }), []);
  assert.equal(search(rows, '', { minResolution: 10000 })[0].id, 'ph-aarfontein_dawn_2');
});

test('the files to download: a model with its textures, an HDRI at the size asked, the maps of a texture', () => {
  const model = { gltf: { '2k': { gltf: { url: 'https://dl.polyhaven.org/f/ArmChair_01_2k.gltf', include: { 'ArmChair_01.bin': { url: 'https://dl.polyhaven.org/f/ArmChair_01.bin' }, 'textures/diff_2k.jpg': { url: 'https://dl.polyhaven.org/f/diff_2k.jpg' } } } }, '4k': { gltf: { url: 'x', include: {} } } } };
  assert.deepEqual(pickFiles('model', model, { res: '2k' }).map((f) => f.path), ['ArmChair_01_2k.gltf', 'ArmChair_01.bin', 'textures/diff_2k.jpg']);
  const hdri = { hdri: { '1k': { hdr: { url: 'https://dl/x_1k.hdr' } }, '4k': { hdr: { url: 'https://dl/x_4k.hdr' } } } };
  assert.equal(pickFiles('hdri', hdri, { res: '4k' })[0].path, 'x_4k.hdr');
  assert.equal(pickFiles('hdri', hdri, { res: '2k' })[0].path, 'x_1k.hdr');   // the nearest size that exists
  const tex = { Diffuse: { '2k': { jpg: { url: 'https://dl/a_diff.jpg' } } }, nor_gl: { '2k': { jpg: { url: 'https://dl/a_nor.jpg' } } }, Rough: { '2k': { png: { url: 'https://dl/a_rough.png' } } } };
  assert.deepEqual(pickFiles('texture', tex).map((f) => f.path), ['diffuse.jpg', 'normal.jpg', 'roughness.png']);
  assert.throws(() => pickFiles('model', {}), /no glTF/);
});

const fakeApi = (n) => async (url) => {
  const t = new URL(url).searchParams.get('t');
  const body = Object.fromEntries(Array.from({ length: n }, (_, i) => [`${t}_${i}`, { name: `${t} ${i}`, tags: [t], categories: [t], authors: { A: 'All' } }]));
  return { ok: true, status: 200, json: async () => body };
};

test('sync writes the register, and leaves it alone when the list looks too small', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'ar-'));
  assert.equal((await listAssets(fakeApi(2))).length, 6);
  const ok = await sync({ dir, fetchFn: fakeApi(150) });
  assert.equal(ok.errors.length, 0); assert.equal(loadCatalog(dir).length, 450); assert.equal(ok.new, 450);
  const bad = await sync({ dir, fetchFn: fakeApi(5) });
  assert.match(bad.errors[0], /only 15 assets/); assert.equal(loadCatalog(dir).length, 450);
});
