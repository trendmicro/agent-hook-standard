import { readFile, readdir, stat } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import Ajv2020 from 'ajv/dist/2020.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const schemaDirectory = path.join(root, 'schemas');
const fixtureDirectory = path.join(root, 'fixtures');
const rfcDirectory = path.join(root, 'rfcs');
const ignoredDirectories = new Set(['.git', 'node_modules', 'build', '.docusaurus']);
const errors = [];

async function filesUnder(directory, predicate = () => true) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      if (!ignoredDirectories.has(entry.name)) files.push(...await filesUnder(target, predicate));
    } else if (predicate(target)) {
      files.push(target);
    }
  }
  return files;
}

async function readJson(file) {
  try {
    return JSON.parse(await readFile(file, 'utf8'));
  } catch (error) {
    errors.push(`${path.relative(root, file)} is not valid JSON: ${error.message}`);
    return null;
  }
}

async function checkMarkdownLinks(markdown, file) {
  const checks = [];
  for (const match of markdown.matchAll(/!?\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)/g)) {
    const destination = match[1].replace(/^<|>$/g, '');
    if (/^(https?:|mailto:|#)/.test(destination)) continue;
    const [target] = destination.split('#');
    if (!target) continue;
    const resolved = path.resolve(path.dirname(file), target);
    checks.push(stat(resolved).catch(() => errors.push(`${path.relative(root, file)} links to missing ${destination}`)));
  }
  await Promise.all(checks);
}

async function validateMarkdownLinks() {
  const markdownFiles = await filesUnder(root, (file) => file.endsWith('.md'));
  await Promise.all(markdownFiles.map(async (file) => checkMarkdownLinks(await readFile(file, 'utf8'), file)));
}

function parseFrontMatter(content) {
  const match = content.match(/^---\n([\s\S]*?)\n---\n/);
  if (!match) return null;
  return match[1];
}

async function validateRfcs() {
  const rfcFiles = (await filesUnder(rfcDirectory, (file) => /^\d{4}-.+\.md$/.test(path.basename(file))))
    .filter((file) => path.basename(file) !== '0000-template.md');
  const requiredFields = ['title:', 'status:', 'discussion:', 'review-start:', 'review-end:', 'maintainer-votes:', 'decision:'];
  for (const file of rfcFiles) {
    const frontMatter = parseFrontMatter(await readFile(file, 'utf8'));
    if (!frontMatter) {
      errors.push(`${path.relative(root, file)} needs YAML front matter`);
      continue;
    }
    for (const field of requiredFields) {
      if (!frontMatter.includes(`\n${field}`) && !frontMatter.startsWith(field)) {
        errors.push(`${path.relative(root, file)} is missing ${field.slice(0, -1)} in front matter`);
      }
    }
  }
}

async function validateSchemasAndFixtures() {
  const schemaFiles = await filesUnder(schemaDirectory, (file) => file.endsWith('.schema.json'));
  const schemas = new Map();
  const ajv = new Ajv2020({ allErrors: true, strict: false });

  for (const file of schemaFiles) {
    const schema = await readJson(file);
    if (!schema) continue;
    const label = path.relative(root, file);
    if (schema.$schema !== 'https://json-schema.org/draft/2020-12/schema') errors.push(`${label} must declare JSON Schema Draft 2020-12`);
    if (typeof schema.$id !== 'string' || !schema.$id) errors.push(`${label} must declare a stable $id`);
    if (typeof schema.title !== 'string' || !schema.title) errors.push(`${label} must declare a title`);
    try {
      schemas.set(path.basename(file, '.schema.json'), ajv.compile(schema));
    } catch (error) {
      errors.push(`${label} is not a compilable schema: ${error.message}`);
    }
  }

  const fixtureNames = new Set((await readdir(fixtureDirectory, { withFileTypes: true }))
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name));
  for (const name of fixtureNames) {
    if (!schemas.has(name)) errors.push(`fixtures/${name} has no matching schemas/${name}.schema.json`);
  }

  for (const [name, validate] of schemas) {
    const base = path.join(fixtureDirectory, name);
    for (const expected of ['valid', 'invalid']) {
      try {
        const files = await filesUnder(path.join(base, expected), (file) => file.endsWith('.json'));
        for (const file of files) {
          const fixture = await readJson(file);
          if (fixture === null) continue;
          const passes = validate(fixture);
          if (passes !== (expected === 'valid')) {
            errors.push(`${path.relative(root, file)} should ${expected === 'valid' ? 'validate' : 'fail validation'} against ${name}.schema.json`);
          }
        }
      } catch (error) {
        if (error.code !== 'ENOENT') throw error;
      }
    }
  }
}

await validateMarkdownLinks();
await validateRfcs();
await validateSchemasAndFixtures();

if (errors.length) {
  console.error(`Validation failed:\n- ${errors.join('\n- ')}`);
  process.exitCode = 1;
} else {
  console.log('Validation passed.');
}
