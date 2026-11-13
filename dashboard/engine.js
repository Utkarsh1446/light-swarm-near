/* Browser and Node engine for the five light agents.
   Float32 math follows the Python prior. Random follows CPython 3.12. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.LightEngine = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  const OPS = ["rot90", "rot180", "rot270", "flip_h", "flip_v", "transpose", "cycle_fg", "fg_to_one", "invert_fg", "swap_top2", "crop_bbox", "keep_largest", "paint_largest", "gravity_down", "gravity_right", "tile2"];
  const GEO = OPS.slice(0, 6);
  const COLOUR = OPS.slice(6, 10);
  const OBJECT = OPS.slice(10, 16);
  const FAMILY = {};
  GEO.forEach((name) => { FAMILY[name] = "geo"; });
  COLOUR.forEach((name) => { FAMILY[name] = "colour"; });
  OBJECT.forEach((name) => { FAMILY[name] = "object"; });

  function PythonRandom(seed) {
    this.mt = new Uint32Array(624);
    this.index = 624;
    this.seed(seed >>> 0);
  }
  PythonRandom.prototype.seed = function (seed) {
    const words = [];
    let n = Math.abs(seed);
    if (n === 0) words.push(0);
    while (n > 0) {
      words.push(n >>> 0);
      n = Math.floor(n / 4294967296);
    }
    this.initByArray(words);
  };
  PythonRandom.prototype.initGenrand = function (s) {
    this.mt[0] = s >>> 0;
    for (let i = 1; i < 624; i += 1) {
      const prev = this.mt[i - 1];
      this.mt[i] = (Math.imul(1812433253, prev ^ (prev >>> 30)) + i) >>> 0;
    }
    this.index = 624;
  };
  PythonRandom.prototype.initByArray = function (key) {
    this.initGenrand(19650218);
    let i = 1;
    let j = 0;
    let k = Math.max(624, key.length);
    for (; k; k -= 1) {
      const prev = this.mt[i - 1];
      this.mt[i] = ((this.mt[i] ^ Math.imul(prev ^ (prev >>> 30), 1664525)) + key[j] + j) >>> 0;
      i += 1;
      j += 1;
      if (i >= 624) { this.mt[0] = this.mt[623]; i = 1; }
      if (j >= key.length) j = 0;
    }
    for (k = 623; k; k -= 1) {
      const prev = this.mt[i - 1];
      this.mt[i] = ((this.mt[i] ^ Math.imul(prev ^ (prev >>> 30), 1566083941)) - i) >>> 0;
      i += 1;
      if (i >= 624) { this.mt[0] = this.mt[623]; i = 1; }
    }
    this.mt[0] = 0x80000000;
    this.index = 624;
  };
  PythonRandom.prototype.next = function () {
    if (this.index >= 624) {
      for (let kk = 0; kk < 624; kk += 1) {
        const y = (this.mt[kk] & 0x80000000) | (this.mt[(kk + 1) % 624] & 0x7fffffff);
        let next = this.mt[(kk + 397) % 624] ^ (y >>> 1);
        if (y & 1) next ^= 0x9908b0df;
        this.mt[kk] = next;
      }
      this.index = 0;
    }
    let y = this.mt[this.index];
    this.index += 1;
    y ^= y >>> 11;
    y ^= (y << 7) & 0x9d2c5680;
    y ^= (y << 15) & 0xefc60000;
    y ^= y >>> 18;
    return y >>> 0;
  };
  PythonRandom.prototype.random = function () {
    const a = this.next() >>> 5;
    const b = this.next() >>> 6;
    return (a * 67108864 + b) / 9007199254740992;
  };
  PythonRandom.prototype.getrandbits = function (k) {
    return this.next() >>> (32 - k);
  };
  PythonRandom.prototype.randrange = function (n) {
    const bits = 32 - Math.clz32(n);
    let value = this.getrandbits(bits);
    while (value >= n) value = this.getrandbits(bits);
    return value;
  };
  PythonRandom.prototype.randint = function (lo, hi) {
    return lo + this.randrange(hi - lo + 1);
  };

  function clone(grid) { return grid.map((row) => row.slice()); }
  function shape(grid) { return [grid.length, grid[0].length]; }

  function objects(grid) {
    const [height, width] = shape(grid);
    const seen = grid.map((row) => row.map(() => false));
    const found = [];
    for (let row = 0; row < height; row += 1) {
      for (let col = 0; col < width; col += 1) {
        if (!grid[row][col] || seen[row][col]) continue;
        const colour = grid[row][col];
        const stack = [[row, col]];
        seen[row][col] = true;
        const cells = [];
        while (stack.length) {
          const [y, x] = stack.pop();
          cells.push([y, x]);
          [[1, 0], [-1, 0], [0, 1], [0, -1]].forEach(([dy, dx]) => {
            const ny = y + dy;
            const nx = x + dx;
            if (ny >= 0 && ny < height && nx >= 0 && nx < width && !seen[ny][nx] && grid[ny][nx] === colour) {
              seen[ny][nx] = true;
              stack.push([ny, nx]);
            }
          });
        }
        found.push(cells);
      }
    }
    return found;
  }

  function bestObject(grid) {
    const comps = objects(grid);
    if (!comps.length) return null;
    return comps.reduce((best, cells) => {
      const key = [cells.length, -Math.min(...cells.map((cell) => cell[0])), -Math.min(...cells.map((cell) => cell[1]))];
      if (!best) return { cells, key };
      if (key[0] > best.key[0] || (key[0] === best.key[0] && (key[1] > best.key[1] || (key[1] === best.key[1] && key[2] > best.key[2])))) {
        return { cells, key };
      }
      return best;
    }, null).cells;
  }

  function rot90(grid) {
    const [height, width] = shape(grid);
    const out = Array.from({ length: width }, () => Array(height).fill(0));
    for (let row = 0; row < height; row += 1) {
      for (let col = 0; col < width; col += 1) out[col][height - 1 - row] = grid[row][col];
    }
    return out;
  }
  function rot180(grid) { return rot90(rot90(grid)); }
  function rot270(grid) { return rot90(rot180(grid)); }
  function flipH(grid) { return grid.map((row) => row.slice().reverse()); }
  function flipV(grid) { return grid.slice().reverse().map((row) => row.slice()); }
  function transpose(grid) {
    const [height, width] = shape(grid);
    return Array.from({ length: width }, (_, col) => Array.from({ length: height }, (_, row) => grid[row][col]));
  }
  function mapCells(grid, fn) {
    return grid.map((row) => row.map(fn));
  }
  function cycleFg(grid) { return mapCells(grid, (value) => (value === 0 ? 0 : value === 9 ? 1 : value + 1)); }
  function fgToOne(grid) { return mapCells(grid, (value) => (value === 0 ? 0 : 1)); }
  function invertFg(grid) { return mapCells(grid, (value) => (value === 0 ? 0 : 10 - value)); }
  function swapTop2(grid) {
    const counts = {};
    grid.forEach((row) => row.forEach((value) => { if (value) counts[value] = (counts[value] || 0) + 1; }));
    const ranking = Object.keys(counts).map(Number).sort((a, b) => counts[b] - counts[a] || a - b);
    if (ranking.length < 2) return null;
    const left = ranking[0];
    const right = ranking[1];
    return mapCells(grid, (value) => (value === left ? right : value === right ? left : value));
  }
  function cropBbox(grid) {
    const cells = [];
    grid.forEach((row, r) => row.forEach((value, c) => { if (value) cells.push([r, c]); }));
    if (!cells.length) return null;
    const r0 = Math.min(...cells.map((cell) => cell[0]));
    const r1 = Math.max(...cells.map((cell) => cell[0]));
    const c0 = Math.min(...cells.map((cell) => cell[1]));
    const c1 = Math.max(...cells.map((cell) => cell[1]));
    return grid.slice(r0, r1 + 1).map((row) => row.slice(c0, c1 + 1));
  }
  function keepLargest(grid) {
    const best = bestObject(grid);
    if (!best) return null;
    const out = grid.map((row) => row.map(() => 0));
    best.forEach(([row, col]) => { out[row][col] = grid[row][col]; });
    return out;
  }
  function paintLargest(grid) {
    const best = bestObject(grid);
    if (!best) return null;
    const out = clone(grid);
    best.forEach(([row, col]) => { out[row][col] = 1; });
    return out;
  }
  function gravityDown(grid) {
    const [height, width] = shape(grid);
    const out = Array.from({ length: height }, () => Array(width).fill(0));
    for (let col = 0; col < width; col += 1) {
      const values = [];
      for (let row = 0; row < height; row += 1) if (grid[row][col]) values.push(grid[row][col]);
      values.forEach((value, offset) => { out[height - values.length + offset][col] = value; });
    }
    return out;
  }
  function gravityRight(grid) {
    return grid.map((row) => {
      const values = row.filter((value) => value);
      const out = Array(row.length).fill(0);
      values.forEach((value, offset) => { out[row.length - values.length + offset] = value; });
      return out;
    });
  }
  function tile2(grid) {
    const [height, width] = shape(grid);
    if (height * 2 > 30 || width * 2 > 30) return null;
    const out = Array.from({ length: height * 2 }, () => Array(width * 2).fill(0));
    for (let row = 0; row < height; row += 1) {
      for (let col = 0; col < width; col += 1) {
        const value = grid[row][col];
        out[row][col] = value;
        out[row][col + width] = value;
        out[row + height][col] = value;
        out[row + height][col + width] = value;
      }
    }
    return out;
  }
  const OP_FN = { rot90, rot180, rot270, flip_h: flipH, flip_v: flipV, transpose, cycle_fg: cycleFg, fg_to_one: fgToOne, invert_fg: invertFg, swap_top2: swapTop2, crop_bbox: cropBbox, keep_largest: keepLargest, paint_largest: paintLargest, gravity_down: gravityDown, gravity_right: gravityRight, tile2 };

  function applyOp(grid, name) {
    const produced = OP_FN[name](grid);
    if (!produced || produced.length > 30 || produced[0].length > 30) return null;
    return produced;
  }
  function applyProgram(grid, program) {
    let current = grid;
    for (const name of program) {
      current = applyOp(current, name);
      if (!current) return null;
    }
    return current;
  }
  function sameGrid(left, right) {
    if (!left || !right || left.length !== right.length) return false;
    return left.every((row, r) => row.length === right[r].length && row.every((value, c) => value === right[r][c]));
  }
  function canonical(grid) { return grid.map((row) => row.join("")).join(";"); }
  function parseGrid(text) { return text.split(";").map((row) => row.split("").map(Number)); }

  function f32(value) { return Math.fround(value); }

  function featurize(demos, maskResidual) {
    const features = new Float32Array(64);
    if (!demos.length) return features;
    const gridIn = demos[0][0];
    const gridOut = demos[0][1];
    const heightIn = gridIn.length;
    const widthIn = gridIn[0].length;
    const heightOut = gridOut.length;
    const widthOut = gridOut[0].length;
    features[0] = f32(heightIn / 12);
    features[1] = f32(widthIn / 12);
    features[2] = f32(heightOut / 12);
    features[3] = f32(widthOut / 12);
    features[4] = heightIn === heightOut && widthIn === widthOut ? 1 : 0;
    const hist = (grid, offset) => {
      const counts = new Float32Array(10);
      let total = 0;
      grid.forEach((row) => row.forEach((value) => { counts[value] = f32(counts[value] + 1); total += 1; }));
      const denom = Math.max(total, 1);
      for (let i = 0; i < 10; i += 1) features[offset + i] = f32(counts[i] / denom);
    };
    hist(gridIn, 5);
    hist(gridOut, 15);
    let l1 = 0;
    for (let i = 0; i < 10; i += 1) l1 += Math.abs(features[5 + i] - features[15 + i]);
    features[25] = f32(l1);
    if (features[4] === 1) {
      let changed = 0;
      for (let row = 0; row < heightIn; row += 1) {
        for (let col = 0; col < widthIn; col += 1) if (gridIn[row][col] !== gridOut[row][col]) changed += 1;
      }
      features[26] = f32(changed / (heightIn * widthIn));
    } else features[26] = 1;
    const center = (grid) => {
      let mass = 0;
      let rowAcc = 0;
      let colAcc = 0;
      grid.forEach((row, r) => row.forEach((value, c) => { if (value) { mass += 1; rowAcc += r; colAcc += c; } }));
      if (!mass) return [0.5, 0.5];
      return [rowAcc / mass / grid.length, colAcc / mass / grid[0].length];
    };
    const [inR, inC] = center(gridIn);
    const [outR, outC] = center(gridOut);
    features[27] = f32(inR);
    features[28] = f32(inC);
    features[29] = f32(outR);
    features[30] = f32(outC);
    features[31] = f32(Math.abs(inR - outR));
    features[32] = f32(Math.abs(inC - outC));
    if (!maskResidual) {
      OPS.forEach((name, index) => {
        const produced = applyProgram(gridIn, [name]);
        let score = 0;
        if (produced && produced.length === heightOut && produced[0].length === widthOut) {
          let same = 0;
          for (let row = 0; row < heightOut; row += 1) {
            for (let col = 0; col < widthOut; col += 1) if (produced[row][col] === gridOut[row][col]) same += 1;
          }
          score = same / (heightOut * widthOut);
        }
        features[33 + index] = f32(score);
      });
    }
    return features;
  }

  function decodeWeights(packed) {
    const read = (b64) => {
      const binary = atob(b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
      const out = new Float32Array(bytes.length / 4);
      const view = new DataView(bytes.buffer);
      for (let i = 0; i < out.length; i += 1) out[i] = view.getFloat32(i * 4, true);
      return out;
    };
    return {
      name: packed.name,
      curiosity: packed.curiosity,
      dims: packed.dims,
      weights: packed.weights_b64.map(read),
      biases: packed.bias_b64.map(read),
    };
  }

  function logits(model, features) {
    let hidden = features;
    const last = model.weights.length - 1;
    for (let layer = 0; layer < model.weights.length; layer += 1) {
      const weight = model.weights[layer];
      const bias = model.biases[layer];
      const rows = layer === 0 ? model.dims[0] : model.dims[layer];
      const cols = model.dims[layer + 1];
      const next = new Float32Array(cols);
      for (let col = 0; col < cols; col += 1) {
        let sum = bias[col];
        for (let row = 0; row < rows; row += 1) sum += hidden[row] * weight[row * cols + col];
        next[col] = layer === last ? sum : (sum > 0 ? sum : 0);
      }
      hidden = next;
    }
    return hidden;
  }

  function behavior(demos, program) {
    return demos.map(([grid]) => {
      const produced = applyProgram(grid, program);
      if (!produced) return "none";
      return produced.map((row) => row.join("")).join(";");
    }).join("|");
  }

  function searchTrace(model, demos, options) {
    const curiosity = options.curiosity == null ? model.curiosity : options.curiosity;
    const beam = options.beam || 6;
    const budget = options.budget || 48;
    const archive = options.archive || new Set();
    const features = featurize(demos, true);
    const scores = logits(model, features);
    const decorated = OPS.map((name, index) => {
      const seen = archive.has(behavior(demos, [name]));
      const bonus = seen ? 0 : curiosity;
      return { name, index, logit: scores[index], bonus, total: scores[index] + bonus };
    });
    decorated.sort((a, b) => b.total - a.total || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
    decorated.slice(0, beam).forEach((item) => archive.add(behavior(demos, [item.name])));
    const top = decorated.slice(0, beam).map((item) => item.name);
    const programs = top.map((name) => [name]);
    const rank = {};
    top.forEach((name, index) => { rank[name] = top.length - index; });
    const pairs = [];
    top.forEach((left) => top.forEach((right) => pairs.push([left, right])));
    pairs.sort((a, b) => (rank[b[0]] + rank[b[1]]) - (rank[a[0]] + rank[a[1]]) || (a < b ? -1 : 1));
    programs.push(...pairs);
    const tried = [];
    let chosen = null;
    programs.slice(0, budget).forEach((program) => {
      if (chosen) return;
      const fits = demos.every(([gridIn, gridOut]) => sameGrid(applyProgram(gridIn, program), gridOut));
      tried.push({ program, fits });
      if (fits) chosen = program;
    });
    return { ranking: decorated, tried, chosen, archive };
  }

  function predict(model, task, options) {
    const demos = task.demos.map((pair) => [parseGrid(pair.in), parseGrid(pair.out)]);
    const trace = searchTrace(model, demos, options || {});
    const testIn = parseGrid(task.test_input);
    const predicted = trace.chosen ? applyProgram(testIn, trace.chosen) : null;
    const answer = parseGrid(task.test_output);
    return {
      ranking: trace.ranking,
      tried: trace.tried,
      program: trace.chosen,
      predicted: predicted ? canonical(predicted) : null,
      correct: Boolean(predicted && sameGrid(predicted, answer)),
    };
  }

  const OBJECT_NORMAL = ["crop_bbox", "keep_largest", "gravity_down", "gravity_right", "tile2"];
  const CROSS_PROGRAMS = [["rot90", "fg_to_one"], ["flip_h", "cycle_fg"], ["transpose", "invert_fg"], ["rot180", "swap_top2"], ["flip_v", "fg_to_one"], ["gravity_down", "cycle_fg"]];

  function programsIn(ops) {
    const singles = ops.map((op) => [op]);
    const pairs = [];
    ops.forEach((left) => ops.forEach((right) => pairs.push([left, right])));
    return singles.concat(pairs);
  }
  function fitsDemos(program, demos) {
    return demos.every(([gridIn, gridOut]) => sameGrid(applyProgram(gridIn, program), gridOut));
  }
  function firstDemoFit(demos, programs) {
    return programs.find((program) => fitsDemos(program, demos)) || null;
  }
  function anyDemoFit(demos, ops) {
    return firstDemoFit(demos, programsIn(ops)) !== null;
  }
  function firstThatGeneralises(demos, testIn, testOut, ops) {
    const found = firstDemoFit(demos, programsIn(ops));
    if (!found) return false;
    return sameGrid(applyProgram(testIn, found), testOut);
  }
  function inferMap(demos) {
    const mapping = {};
    for (const [gridIn, gridOut] of demos) {
      if (gridIn.length !== gridOut.length || gridIn[0].length !== gridOut[0].length) return null;
      for (let row = 0; row < gridIn.length; row += 1) {
        for (let col = 0; col < gridIn[0].length; col += 1) {
          const src = gridIn[row][col];
          const dst = gridOut[row][col];
          if (mapping[src] !== undefined && mapping[src] !== dst) return null;
          mapping[src] = dst;
        }
      }
    }
    const keys = Object.keys(mapping);
    if (!keys.length || keys.every((key) => Number(key) === mapping[key])) return null;
    return mapping;
  }
  function applyMap(grid, mapping) {
    return grid.map((row) => row.map((value) => (mapping[value] === undefined ? value : mapping[value])));
  }
  function paintRect(grid, row, col, height, width, colour) {
    for (let r = row; r < Math.min(grid.length, row + height); r += 1) {
      for (let c = col; c < Math.min(grid[0].length, col + width); c += 1) grid[r][c] = colour;
    }
  }
  function randomGrid(rng, maxSide) {
    const height = rng.randint(3, maxSide);
    const width = rng.randint(3, maxSide);
    const colours = rng.randint(2, 5);
    const grid = Array.from({ length: height }, () => Array(width).fill(0));
    let nonzero = 0;
    for (let row = 0; row < height; row += 1) {
      for (let col = 0; col < width; col += 1) {
        if (rng.random() < 0.65) {
          grid[row][col] = rng.randint(1, colours);
          nonzero += 1;
        }
      }
    }
    if (nonzero < 4) {
      grid[0][0] = 1;
      grid[0][1] = 2;
      grid[1][0] = 2;
      grid[1][1] = 1;
    }
    return grid;
  }
  function embed(rng, inner) {
    const height = inner.length;
    const width = inner[0].length;
    const canvasH = height + 2;
    const canvasW = width + 2;
    const grid = Array.from({ length: canvasH }, () => Array(canvasW).fill(0));
    const row0 = rng.randrange(canvasH - height + 1);
    const col0 = rng.randrange(canvasW - width + 1);
    for (let row = 0; row < height; row += 1) {
      for (let col = 0; col < width; col += 1) grid[row0 + row][col0 + col] = inner[row][col];
    }
    return grid;
  }
  function gridFor(rng, program) {
    const op = program[0];
    if (op === "crop_bbox" || (program.length > 1 && program[1] === "crop_bbox")) return embed(rng, randomGrid(rng, 3));
    if (op === "tile2") return randomGrid(rng, 3);
    const grid = randomGrid(rng, 5);
    if (op === "gravity_down") {
      for (let col = 0; col < grid[0].length; col += 1) grid[grid.length - 1][col] = 0;
    } else if (op === "gravity_right") {
      grid.forEach((row) => { row[row.length - 1] = 0; });
    }
    return grid;
  }
  function fromProgram(rng, family, program) {
    const inputs = [];
    for (let attempt = 0; attempt < 30 && inputs.length < 3; attempt += 1) {
      const grid = gridFor(rng, program);
      const output = applyProgram(grid, program);
      if (!output || sameGrid(output, grid)) continue;
      if (output.length > 12 || output[0].length > 12) continue;
      inputs.push([grid, output]);
    }
    if (inputs.length < 3) return null;
    return { family, program, demos: inputs.slice(0, 2), testIn: inputs[2][0], testOut: inputs[2][1] };
  }
  function accept(task) {
    if (task.family === "trap") {
      const mapping = inferMap(task.demos);
      if (!mapping || sameGrid(applyMap(task.testIn, mapping), task.testOut)) return false;
      if (anyDemoFit(task.demos, GEO) || anyDemoFit(task.demos, COLOUR)) return false;
      return firstThatGeneralises(task.demos, task.testIn, task.testOut, OBJECT);
    }
    if (task.family === "cross") {
      if ([GEO, COLOUR, OBJECT].some((ops) => anyDemoFit(task.demos, ops))) return false;
      return sameGrid(applyProgram(task.testIn, task.program), task.testOut);
    }
    const own = { geo: GEO, colour: COLOUR, object: OBJECT }[task.family];
    const others = [["geo", GEO], ["colour", COLOUR], ["object", OBJECT]].filter(([name]) => name !== task.family).map((pair) => pair[1]);
    if (!firstThatGeneralises(task.demos, task.testIn, task.testOut, own)) return false;
    if (others.some((ops) => anyDemoFit(task.demos, ops))) return false;
    const mapping = inferMap(task.demos);
    if (task.family !== "colour" && mapping) return false;
    if (task.family === "colour" && (!mapping || !sameGrid(applyMap(task.testIn, mapping), task.testOut))) return false;
    return true;
  }
  function tryTrap(rng) {
    const demos = [];
    for (let i = 0; i < 2; i += 1) {
      const grid = Array.from({ length: 6 }, () => Array(6).fill(0));
      paintRect(grid, rng.randrange(2), rng.randrange(2), 3, 3, 2);
      paintRect(grid, rng.randrange(1) + 4, rng.randrange(1) + 4, 2, 1, 3);
      const output = applyProgram(grid, ["paint_largest"]);
      if (!output || sameGrid(output, grid)) return null;
      demos.push([grid, output]);
    }
    const test = Array.from({ length: 6 }, () => Array(6).fill(0));
    paintRect(test, 0, 0, 3, 3, 2);
    paintRect(test, 4, 4, 1, 2, 2);
    if (rng.random() < 0.5) {
      paintRect(test, 0, 0, 3, 2, 2);
      paintRect(test, 4, 3, 2, 1, 2);
    }
    const testOut = applyProgram(test, ["paint_largest"]);
    if (!testOut || sameGrid(testOut, test)) return null;
    return { family: "trap", program: ["paint_largest"], demos, testIn: test, testOut };
  }
  function generateTask(family, rng, attempts) {
    const limit = attempts || 80;
    for (let i = 0; i < limit; i += 1) {
      let task = null;
      if (family === "trap") task = tryTrap(rng);
      else if (family === "cross") {
        const program = CROSS_PROGRAMS[rng.randrange(CROSS_PROGRAMS.length)];
        if (FAMILY[program[0]] !== FAMILY[program[1]]) task = fromProgram(rng, "cross", program);
      } else if (family === "geo") task = fromProgram(rng, "geo", [GEO[rng.randrange(GEO.length)]]);
      else if (family === "colour") task = fromProgram(rng, "colour", [COLOUR[rng.randrange(COLOUR.length)]]);
      else if (family === "object") task = fromProgram(rng, "object", [OBJECT_NORMAL[rng.randrange(OBJECT_NORMAL.length)]]);
      else throw new Error("unknown family " + family);
      if (task && accept(task)) return task;
    }
    throw new Error("could not sample a " + family + " task");
  }
  function packTask(task) {
    return {
      family: task.family,
      program: task.program,
      demos: task.demos.map(([gridIn, gridOut]) => ({ in: canonical(gridIn), out: canonical(gridOut) })),
      test_input: canonical(task.testIn),
      test_output: canonical(task.testOut),
    };
  }

  return {
    OPS, FAMILY, PythonRandom, featurize, decodeWeights, logits, searchTrace, predict,
    parseGrid, canonical, applyProgram, generateTask, packTask,
  };
});
