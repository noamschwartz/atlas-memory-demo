#!/usr/bin/env node
/**
 * EUI Icon Cache Generator
 * 
 * Scans the codebase for iconType usage and generates iconCache.ts
 * Run: node scripts/generate-icon-cache.js
 * 
 * This solves the brittle manual icon cache problem by:
 * 1. Scanning all .tsx/.ts files for iconType="..." patterns
 * 2. Checking which icon assets actually exist in EUI
 * 3. Generating a complete iconCache.ts file
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Configuration
const SRC_DIR = path.join(__dirname, '../src');
const OUTPUT_FILE = path.join(SRC_DIR, 'iconCache.ts');
const EUI_ICONS_DIR = path.join(__dirname, '../node_modules/@elastic/eui/es/components/icon/assets');

// Icons that EUI components use internally (hidden dependencies)
const INTERNAL_ICONS = [
  'apps',           // EuiCard
  'arrowDown',      // EuiAccordion, EuiSelect
  'arrowUp',        // EuiAccordion
  'arrowRight',     // Various
  'arrowLeft',      // Various
  'check',          // EuiCheckbox, EuiSwitch, status
  'cross',          // EuiModal close, EuiBadge
  'empty',          // EuiEmptyPrompt, fallbacks
  'popout',         // EuiLink external
  'warning',        // EuiCallOut
  'clock',          // Status badges
  'checkInCircleFilled',  // Status
  'crossInCircle',  // Status
  'menu',           // EuiHeader
  'search',         // EuiSearchBar
  'moon',           // Theme toggle
  'sun',            // Theme toggle
];

// Convert camelCase to snake_case for file lookup
function toSnakeCase(str) {
  return str.replace(/([A-Z])/g, '_$1').toLowerCase().replace(/^_/, '');
}

// Check if icon asset exists
function iconExists(iconName) {
  const snakeName = toSnakeCase(iconName);
  const possibleFiles = [
    path.join(EUI_ICONS_DIR, `${snakeName}.js`),
    path.join(EUI_ICONS_DIR, `${iconName}.js`),
  ];
  return possibleFiles.some(f => fs.existsSync(f));
}

// Get the correct import path for an icon
function getIconImportPath(iconName) {
  const snakeName = toSnakeCase(iconName);
  const snakePath = path.join(EUI_ICONS_DIR, `${snakeName}.js`);
  const directPath = path.join(EUI_ICONS_DIR, `${iconName}.js`);
  
  if (fs.existsSync(snakePath)) return snakeName;
  if (fs.existsSync(directPath)) return iconName;
  return null;
}

// Scan a file for iconType usages
function scanFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  const icons = new Set();
  
  // Match iconType="..." and iconType={'...'}
  const patterns = [
    /iconType=["']([^"']+)["']/g,
    /iconType=\{["']([^"']+)["']\}/g,
    /type=["']([^"']+)["']/g,  // EuiIcon type prop
  ];
  
  for (const pattern of patterns) {
    let match;
    while ((match = pattern.exec(content)) !== null) {
      const iconName = match[1];
      // Skip dynamic values and non-icon strings
      if (!iconName.includes('{') && !iconName.includes('$') && iconName.length < 50) {
        icons.add(iconName);
      }
    }
  }
  
  return icons;
}

// Recursively scan directory
function scanDirectory(dir) {
  const allIcons = new Set();
  
  function walk(currentDir) {
    const files = fs.readdirSync(currentDir);
    for (const file of files) {
      const filePath = path.join(currentDir, file);
      const stat = fs.statSync(filePath);
      
      if (stat.isDirectory() && !file.includes('node_modules')) {
        walk(filePath);
      } else if (file.endsWith('.tsx') || file.endsWith('.ts')) {
        const icons = scanFile(filePath);
        icons.forEach(icon => allIcons.add(icon));
      }
    }
  }
  
  walk(dir);
  return allIcons;
}

// Generate the iconCache.ts content
function generateIconCache(icons) {
  const validIcons = new Map(); // iconName -> importPath
  const invalidIcons = [];
  
  // Check each found icon
  for (const iconName of icons) {
    const importPath = getIconImportPath(iconName);
    if (importPath) {
      validIcons.set(iconName, importPath);
    } else {
      invalidIcons.push(iconName);
    }
  }
  
  // Add internal icons
  for (const iconName of INTERNAL_ICONS) {
    const importPath = getIconImportPath(iconName);
    if (importPath && !validIcons.has(iconName)) {
      validIcons.set(iconName, importPath);
    }
  }
  
  // Sort icons alphabetically
  const sortedIcons = [...validIcons.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  
  // Generate imports
  const imports = sortedIcons.map(([name, importPath]) => {
    const varName = name.replace(/[^a-zA-Z0-9]/g, '_');
    return `import { icon as ${varName} } from '@elastic/eui/es/components/icon/assets/${importPath}'`;
  });
  
  // Generate cache entries
  const entries = sortedIcons.map(([name, importPath]) => {
    const varName = name.replace(/[^a-zA-Z0-9]/g, '_');
    const snakeName = toSnakeCase(name);
    
    // Add both camelCase and snake_case entries
    if (name !== snakeName) {
      return `  ${varName},\n  ${snakeName}: ${varName},`;
    }
    return `  ${varName},`;
  });
  
  const content = `/**
 * EUI Icon Cache for Vite
 * 
 * AUTO-GENERATED by scripts/generate-icon-cache.js
 * Run: yarn generate-icons (or npm run generate-icons)
 * 
 * This file pre-registers all icons used in the app.
 * EUI icons use dynamic imports which don't work well with Vite.
 * 
 * Generated: ${new Date().toISOString()}
 * Icons found: ${validIcons.size}
 */

import { appendIconComponentCache } from '@elastic/eui/es/components/icon/icon'

${imports.join('\n')}

// Register icons in the cache
appendIconComponentCache({
${entries.join('\n')}
})

// Aliases for common mismatches
appendIconComponentCache({
  discuss: comment,           // 'discuss' doesn't exist, use 'comment'
  crossInCircleFilled: crossInCircle,  // Doesn't exist, use crossInCircle
})
`;

  return { content, validIcons, invalidIcons };
}

// Main
console.log('🔍 Scanning for EUI icons...\n');

const foundIcons = scanDirectory(SRC_DIR);
console.log(`Found ${foundIcons.size} icon references in source files\n`);

const { content, validIcons, invalidIcons } = generateIconCache(foundIcons);

// Write the file
fs.writeFileSync(OUTPUT_FILE, content);
console.log(`✅ Generated ${OUTPUT_FILE}`);
console.log(`   ${validIcons.size} valid icons registered\n`);

if (invalidIcons.length > 0) {
  console.log('⚠️  Invalid icons found (no matching asset):');
  invalidIcons.forEach(icon => console.log(`   - ${icon}`));
  console.log('\n   These need to be replaced with valid icon names.');
  console.log('   Check: ls node_modules/@elastic/eui/es/components/icon/assets/\n');
}

console.log('💡 Add to package.json scripts:');
console.log('   "generate-icons": "node scripts/generate-icon-cache.js"');
console.log('   "prebuild": "npm run generate-icons"');



