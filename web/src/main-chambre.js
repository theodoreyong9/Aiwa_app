import { startChambre } from './chambre.js';

// The chamber has no screen: it lives under the home of the application, driven by the phone (window.aiwaChamber).
startChambre(new URLSearchParams(location.search));
