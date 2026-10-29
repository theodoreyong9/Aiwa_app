import { initVoirPage } from './voir-page.js';
import { bootWallet } from './boot.js';

// « Voir » signs what it publishes with the wallet's key: the wallet starts by itself if the phone has one (without it, one still looks).
bootWallet().catch(() => {}).finally(() => initVoirPage(new URLSearchParams(location.search)));
