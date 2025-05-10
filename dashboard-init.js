jQuery(document).ready(function ($) {
  $('#dashboard').DataTable({
    ajax: {
      url: 'https://aaqil456.github.io/CryptoProject-AutoPost/dashboard.json',
      dataSrc: ''
    },
    columns: [
      { data: 'nama', defaultContent: '-' },
      { data: 'dana', defaultContent: '-' },
      { data: 'fasa', defaultContent: '-' },
      { data: 'ada_token', defaultContent: '-' },
      { data: 'pelabur', defaultContent: '-' },
      { data: 'deskripsi', defaultContent: '-' },
      {
        data: 'twitter',
        defaultContent: '-',
        render: function (data) {
          if (!data || data === "-" || data.trim() === "") return "-";
          return '<a href="https://x.com/' + data.replace('@', '') + '" target="_blank">' + data + '</a>';
        }
      },
      {
        data: 'tweet_url',
        defaultContent: '-',
        render: function (data) {
          return data ? '<a href="' + data + '" target="_blank">🔗</a>' : '-';
        }
      }
    ],
    pageLength: 5,
    language: {
      search: "Cari Projek:",
      lengthMenu: "Papar _MENU_ entri",
      info: "Menunjukkan _START_ hingga _END_ dari _TOTAL_ entri",
      paginate: {
        previous: "Sebelum",
        next: "Seterusnya"
      }
    }
  });
});
