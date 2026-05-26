#!/usr/bin/env node
/**
 * Icon Validation Script (Self-Healing)
 * 
 * Scans the codebase for icon usages and validates they exist in EUI.
 * If a valid EUI icon is missing from the cache, it regenerates the cache.
 * Only fails on actual typos (icons that don't exist in EUI).
 * 
 * Usage: node scripts/validate-icons.cjs
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const SRC_DIR = path.join(__dirname, '../src');
const ICON_CACHE_FILE = path.join(SRC_DIR, 'iconCache.ts');
const EUI_ICONS_DIR = path.join(__dirname, '../node_modules/@elastic/eui/es/components/icon/assets');
const EUI_ICON_MAP = path.join(__dirname, '../node_modules/@elastic/eui/es/components/icon/icon_map.js');

// Patterns to find icon usages
const ICON_PATTERNS = [
  /iconType=["']([^"']+)["']/g,           // iconType="search"
  /icon:\s*["']([^"']+)["']/g,            // icon: 'search'
  /<EuiIcon[^>]*type=["']([^"']+)["']/g,  // <EuiIcon type="search"
  /<EuiButtonIcon[^>]*iconType=["']([^"']+)["']/g,  // <EuiButtonIcon iconType="search"
];

// Icons that are valid but not in our cache (emojis, custom SVGs, etc.)
const IGNORE_PATTERNS = [
  /^[^\w]/,      // Starts with non-word char (emojis)
  /^http/,       // URLs
  /^data:/,      // Data URIs
  /^\//,         // Paths
  /^button$/,    // HTML button type="button"
  /^submit$/,    // HTML button type="submit"
  /^reset$/,     // HTML button type="reset"
  /^text$/,      // HTML input type="text"
  /^number$/,    // HTML input type="number"
  /^checkbox$/,  // HTML input type
  /^radio$/,     // HTML input type
  /^password$/,  // HTML input type
];

/**
 * Get all valid EUI icon names (from assets + aliases)
 */
function getValidEuiIcons() {
  const validIcons = new Set();
  
  // 1. Get all icon asset files
  if (fs.existsSync(EUI_ICONS_DIR)) {
    const files = fs.readdirSync(EUI_ICONS_DIR);
    for (const file of files) {
      if (file.endsWith('.js') && file !== 'index.js') {
        const name = path.basename(file, '.js');
        validIcons.add(name);
        // Also add camelCase version
        const camelName = name.replace(/_([a-z0-9])/g, (g) => g[1].toUpperCase());
        validIcons.add(camelName);
      }
    }
  }
  
  // 2. Get all aliases from icon_map.js
  if (fs.existsSync(EUI_ICON_MAP)) {
    const content = fs.readFileSync(EUI_ICON_MAP, 'utf8');
    const regex = /^\s+(\w+):\s*'([a-z_]+)',/gm;
    let match;
    while ((match = regex.exec(content)) !== null) {
      validIcons.add(match[1]); // alias name
    }
  }
  
  return validIcons;
}

function extractIconsFromFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const icons = new Set();
  
  for (const pattern of ICON_PATTERNS) {
    let match;
    // Reset regex state
    pattern.lastIndex = 0;
    while ((match = pattern.exec(content)) !== null) {
      const icon = match[1];
      // Skip ignored patterns
      if (!IGNORE_PATTERNS.some(p => p.test(icon))) {
        icons.add(icon);
      }
    }
  }
  
  return icons;
}

function getRegisteredIcons() {
  const content = fs.readFileSync(ICON_CACHE_FILE, 'utf8');
  const icons = new Set();
  
  const entryPattern = /^\s*['"]?(\w+)['"]?(?::|,)/gm;
  
  let match;
  while ((match = entryPattern.exec(content)) !== null) {
    icons.add(match[1]);
  }
  
  return icons;
}

function findTsxFiles(dir) {
  const files = [];
  
  function scan(currentDir) {
    const entries = fs.readdirSync(currentDir, { withFileTypes: true });
    
    for (const entry of entries) {
      const fullPath = path.join(currentDir, entry.name);
      
      if (entry.isDirectory() && entry.name !== 'node_modules' && entry.name !== 'dist') {
        scan(fullPath);
      } else if (entry.isFile() && (entry.name.endsWith('.tsx') || entry.name.endsWith('.ts'))) {
        if (!entry.name.includes('iconCache')) {
          files.push(fullPath);
        }
      }
    }
  }
  
  scan(dir);
  return files;
}

function main() {
  console.log('🔍 Validating icon usage...\n');
  
  // Get all valid EUI icons
  const validEuiIcons = getValidEuiIcons();
  console.log(`📚 Found ${validEuiIcons.size} valid EUI icons (assets + aliases)\n`);
  
  // Get registered icons in our cache
  const registeredIcons = getRegisteredIcons();
  console.log(`📦 Found ${registeredIcons.size} icons in iconCache.ts\n`);
  
  // Find all TSX/TS files
  const files = findTsxFiles(SRC_DIR);
  console.log(`📂 Scanning ${files.length} files...\n`);
  
  // Track all used icons
  const allUsedIcons = new Set();
  const missingFromCache = new Map(); // icon -> [files] - valid EUI icons not in cache
  const invalidIcons = new Map();     // icon -> [files] - typos/non-existent icons
  
  for (const file of files) {
    const icons = extractIconsFromFile(file);
    const relativePath = path.relative(SRC_DIR, file);
    
    for (const icon of icons) {
      allUsedIcons.add(icon);
      
      if (!registeredIcons.has(icon)) {
        // Check if it's a valid EUI icon
        if (validEuiIcons.has(icon)) {
          if (!missingFromCache.has(icon)) {
            missingFromCache.set(icon, []);
          }
          missingFromCache.get(icon).push(relativePath);
        } else {
          if (!invalidIcons.has(icon)) {
            invalidIcons.set(icon, []);
          }
          invalidIcons.get(icon).push(relativePath);
        }
      }
    }
  }
  
  console.log(`📊 Found ${allUsedIcons.size} unique icons used in code\n`);
  
  // Handle missing but valid icons - regenerate cache
  if (missingFromCache.size > 0) {
    console.log(`🔧 Found ${missingFromCache.size} valid EUI icons not in cache:\n`);
    for (const [icon, files] of missingFromCache) {
      console.log(`   📎 "${icon}" used in: ${files.join(', ')}`);
    }
    
    console.log('\n🔄 Regenerating icon cache to include them...\n');
    
    try {
      execSync('node scripts/generate-icon-cache.cjs', { 
        cwd: path.join(__dirname, '..'),
        stdio: 'inherit'
      });
      console.log('\n✅ Icon cache regenerated successfully!\n');
    } catch (error) {
      console.error('❌ Failed to regenerate icon cache:', error.message);
      process.exit(1);
    }
  }
  
  // Handle invalid icons (typos) - these are errors
  if (invalidIcons.size > 0) {
    console.log(`❌ Found ${invalidIcons.size} INVALID icons (typos or non-EUI icons):\n`);
    
    for (const [icon, files] of invalidIcons) {
      console.log(`  ⚠️  "${icon}"`);
      for (const file of files) {
        console.log(`      └─ ${file}`);
      }
      
      // Suggest similar valid icons
      const similar = [...validEuiIcons].filter(v => 
        v.toLowerCase().includes(icon.toLowerCase()) || 
        icon.toLowerCase().includes(v.toLowerCase())
      ).slice(0, 3);
      
      if (similar.length > 0) {
        console.log(`      💡 Did you mean: ${similar.join(', ')}?`);
      }
    }
    
    console.log('\n📝 To fix:');
    console.log('   1. Check the icon name spelling (see https://eui.elastic.co/#/display/icons)');
    console.log('   2. Use a valid EUI icon name');
    console.log('   3. If using a custom SVG, pass the component directly instead of a string\n');
    
    process.exit(1);
  }
  
  // All good!
  if (missingFromCache.size === 0) {
    console.log('✅ All icons are registered in iconCache.ts!\n');
  }
  console.log('Your icon setup is bulletproof. 🛡️');
  process.exit(0);
}

main();
