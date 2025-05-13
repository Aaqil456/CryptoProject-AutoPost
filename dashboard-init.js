jQuery(document).ready(function ($) {
  $('#dashboard').DataTable({
    ajax: {
      url: 'https://aaqil456.github.io/CryptoProject-AutoPost/results.json',
      dataSrc: 'data'
    },
    columns: [
      { data: 'dashboard.nama', defaultContent: '-' },
      { data: 'dashboard.dana', defaultContent: '-' },
      { data: 'dashboard.fasa', defaultContent: '-' },
      { data: 'dashboard.ada_token', defaultContent: '-' },
      { data: 'dashboard.pelabur', defaultContent: '-' },
      { data: 'dashboard.deskripsi', defaultContent: '-' },
      {
        data: 'dashboard.twitter',
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
