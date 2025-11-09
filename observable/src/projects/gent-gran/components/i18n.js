export function t(translations, key, params = {}) {
  const value = translations[key];

  if (!value) return `Undef: ${value}`;

  let result = value;
  Object.keys(params).forEach(param => {
    result = result.replace(`{${param}}`, params[param]);
  });

  return result;
}