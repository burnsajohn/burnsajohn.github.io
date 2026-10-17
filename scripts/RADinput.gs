/**
 * Creates the Cell Collection Log: a Google Form linked to a response Sheet.
 * Paste into a new project at script.google.com, then run setupCellLog().
 *
 * Optional: put the Drive ID of your shared data folder in FOLDER_ID
 * (the long string at the end of the folder's URL) to file both items there.
 */
const FOLDER_ID = '1JnoAH2qcrBMs_ftvTh1C_X426wuevX-i';

function setupCellLog() {
  const form = FormApp.create('Cell Collection Log');
  form.setDescription('One entry per cell collected for sequencing.');

  form.addTextItem()
    .setTitle('Cell ID')
    .setHelpText('Unique ID used for this cell in sequencing.')
    .setRequired(true);

  form.addDateItem()
    .setTitle('Collection date')
    .setRequired(true);

  form.addTextItem()
    .setTitle('Day of collection')
    .setHelpText('Day in culture or experiment (e.g., 3).')
    .setValidation(FormApp.createTextValidation()
      .requireNumber()
      .setHelpText('Enter a number.')
      .build());

  form.addMultipleChoiceItem()
    .setTitle('Growth stage')
    .setChoiceValues(['Juvenile', 'Adult', 'Reproductive (gamont)'])
    .showOtherOption(true)
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Genomic sample type')
    .setChoiceValues(['PTA', 'MDA', 'Bulk'])
    .showOtherOption(true)
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('Notes');

  // Linked response sheet. Every submission becomes a new row automatically.
  const ss = SpreadsheetApp.create('Cell Collection Log (responses)');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  // View-only link so people entering data can check the sheet.
  // If your institution blocks public links, change ANYONE_WITH_LINK to DOMAIN_WITH_LINK.
  const sheetFile = DriveApp.getFileById(ss.getId());
  try {
    sheetFile.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
  } catch (e) {
    Logger.log('Could not set link sharing: ' + e.message);
  }

  // Shown after each submission, with a link to the sheet.
  form.setConfirmationMessage(
    'Entry recorded. View the full log here: ' + ss.getUrl());

  if (FOLDER_ID) {
    const folder = DriveApp.getFolderById(FOLDER_ID);
    DriveApp.getFileById(form.getId()).moveTo(folder);
    sheetFile.moveTo(folder);
  }

  Logger.log('Form (edit):  ' + form.getEditUrl());
  Logger.log('Form (share): ' + form.getPublishedUrl());
  Logger.log('Sheet:        ' + ss.getUrl());
}