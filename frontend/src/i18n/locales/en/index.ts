import { about } from './about';
import { agents } from './agents';
import { auth } from './auth';
import { history } from './history';
import { landing } from './landing';
import { legal } from './legal';
import { nav } from './nav';
import { settings } from './settings';
import { workspace } from './workspace';

export const en: Record<string, string> = {
  ...nav,
  ...landing,
  ...settings,
  ...about,
  ...history,
  ...workspace,
  ...agents,
  ...auth,
  ...legal,
};
