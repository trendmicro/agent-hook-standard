import type { SidebarsConfig } from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  specificationSidebar: [
    'index',
    {
      type: 'category',
      label: 'Version 0.1 draft',
      items: [
        '0.1/index',
        '0.1/core',
        '0.1/events',
        '0.1/extensions',
        '0.1/security',
        '0.1/adapters'
      ]
    }
  ]
};

export default sidebars;
